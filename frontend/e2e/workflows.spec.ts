import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { expect, test, type Download, type Page } from '@playwright/test'

const fixture = (name: string) => fileURLToPath(new URL(`.generated/${name}`, import.meta.url))

test.describe.configure({ mode: 'serial' })

test('DOCX watermark workflow reaches verified result and report', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await upload(page, 'browser-watermark.docx')

  await page.getByLabel('目标文字（可选）').fill('DRAFT')
  await page.getByRole('button', { name: '开始扫描' }).click()
  await expect(page.getByRole('heading', { name: 'DRAFT' })).toBeVisible()
  await expect(page.getByText('与目标匹配', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /生成无水印副本/ }).click()

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('docx')
  expect(report.processing.kind).toBe('object_removal')
  expect(report.processing.selected_target_count).toBe(1)
  await expectResultDownload(page, /-cleaned\.docx$/)
  expect(browserErrors).toEqual([])
})

test('general PDF redaction workflow confirms overlap and downloads report', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await upload(page, 'browser-watermark.pdf')

  await page.getByLabel('扫描模式').selectOption('general')
  await page.getByRole('button', { name: '扫描通用 PDF' }).click()
  await expect(page.getByRole('heading', { name: '框选水印并选择处理方式' })).toBeVisible()
  await page.getByLabel('X0', { exact: true }).fill('80')
  await page.getByLabel('Y0', { exact: true }).fill('650')
  await page.getByLabel('X1', { exact: true }).fill('250')
  await page.getByLabel('Y1', { exact: true }).fill('725')
  await page.getByRole('button', { name: '检查区域重叠风险' }).click()

  const overlapConfirmation = page.getByLabel(/我已核对相交对象/)
  await expect(overlapConfirmation).toBeVisible()
  await overlapConfirmation.check()
  await page.getByRole('button', { name: '生成区域删除后的 PDF 副本' }).click()

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('pdf')
  expect(report.processing.kind).toBe('pdf_redaction')
  expect(report.processing.warning_codes).toContain('PDF_REDACTION_OVERLAP')
  await expectResultDownload(page, /-cleaned\.pdf$/)
  expect(browserErrors).toEqual([])
})

test('image mask workflow repairs selected pixels and downloads report', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await upload(page, 'browser-watermark.png')

  await page.getByRole('button', { name: '检查图片并编辑蒙版' }).click()
  const image = page.locator('.image-mask-canvas img')
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).complete)).toBe(true)
  await image.scrollIntoViewIfNeeded()
  const bounds = await image.boundingBox()
  expect(bounds).not.toBeNull()
  if (!bounds) throw new Error('Image editor has no layout bounds.')
  await page.mouse.move(bounds.x + bounds.width * 0.25, bounds.y + bounds.height * 0.33)
  await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width * 0.55, bounds.y + bounds.height * 0.58)
  await page.mouse.up()

  await expect(page.getByText(/区域 1：/)).toBeVisible()
  await page.getByRole('button', { name: '验证蒙版草稿（1 个区域）' }).click()
  await expect(page.getByRole('heading', { name: /背景复杂度/ })).toBeVisible()
  await page.getByRole('button', { name: '使用 OpenCV 生成修复副本' }).click()

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('png')
  expect(report.processing.kind).toBe('image_inpaint')
  expect(report.processing.radius).toBe(3)
  await expectResultDownload(page, /-cleaned\.png$/)
  expect(browserErrors).toEqual([])
})

async function upload(page: Page, name: string) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '看清改动，再处理水印' })).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles(fixture(name))
  await page.getByRole('button', { name: '上传并检查' }).click()
  await expect(page).toHaveURL(/\/workspace\/[0-9a-f-]+$/)
  await expect(page.getByRole('heading', { name })).toBeVisible()
}

async function expectCompleted(page: Page) {
  await expect(page.getByText('处理完成', { exact: true })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('link', { name: '下载处理报告' })).toBeVisible()
}

async function downloadReport(page: Page) {
  const download = await captureDownload(
    page,
    () => page.getByRole('link', { name: '下载处理报告' }).click(),
  )
  expect(download.suggestedFilename()).toMatch(/^task-[0-9a-f]{8}-report\.json$/)
  const path = await download.path()
  if (!path) throw new Error('Task report download did not produce a local file.')
  const report = JSON.parse(await readFile(path, 'utf8'))
  expect(report.schema_version).toBe('1.0')
  expect(report.status).toBe('succeeded')
  expect(JSON.stringify(report)).not.toMatch(/display_name|relative_path|download_url|\/Users\//)
  return report
}

async function expectResultDownload(page: Page, filename: RegExp) {
  const resultLink = page.locator('.result-card .download-button')
  const download = await captureDownload(page, () => resultLink.click())
  expect(download.suggestedFilename()).toMatch(filename)
  expect(await download.path()).not.toBeNull()
}

async function captureDownload(
  page: Page,
  action: () => Promise<unknown>,
): Promise<Download> {
  const [download] = await Promise.all([page.waitForEvent('download'), action()])
  return download
}

function watchBrowserErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text())
  })
  return errors
}
