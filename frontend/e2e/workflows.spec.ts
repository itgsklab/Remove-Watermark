import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { expect, test, type Download, type Page } from '@playwright/test'

const fixture = (name: string) => fileURLToPath(new URL(`.generated/${name}`, import.meta.url))

test.describe.configure({ mode: 'serial' })

test('settings show privacy-safe local runtime diagnostics', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await page.goto('/settings')

  await expect(page.getByRole('heading', { name: '运行环境诊断' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'PDF OCR' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '小红书网络能力' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '本地 VLM' })).toBeVisible()
  await page.getByRole('button', { name: '重新检查' }).click()
  await expect(page.getByRole('button', { name: '重新检查' })).toBeEnabled()

  const summary = page.getByLabel('安全诊断摘要')
  await expect(summary).toBeVisible()
  const payload = JSON.parse(await summary.inputValue())
  expect(payload.schema_version).toBe(2)
  expect(payload.ocr.status).toMatch(/^(unavailable|ready|probe_failed)$/)
  expect(payload.xiaohongshu.status).toBe('parse_only')
  expect(payload.vlm_localization.status).toBe('disabled')
  expect(JSON.stringify(payload)).not.toMatch(
    /display_name|relative_path|download_url|executable|proxy_url|model_dir|\/Users\//,
  )

  await upload(page, 'browser-watermark.pdf')
  await page.getByLabel('扫描模式').selectOption('general')
  await page.getByRole('button', { name: '扫描通用 PDF' }).click()
  await page.getByLabel('处理方式').selectOption('raster_inpaint')
  const ocrToggle = page.getByLabel('为没有原始文字层的页面执行 OCR')
  if (payload.ocr.status === 'ready') {
    await expect(ocrToggle).toBeEnabled()
    await expect(ocrToggle).toBeChecked()
    const languageSelect = page.getByLabel('已安装语言包（可多选）')
    await expect(languageSelect).toBeVisible()
    expect(await languageSelect.locator('option').allTextContents()).toEqual(payload.ocr.languages)
    if (payload.ocr.languages.length > 1) {
      const selected = payload.ocr.languages.slice(0, 2)
      await languageSelect.selectOption(selected)
      await expect(page.getByText(`当前组合：${selected.join('+')}`)).toBeVisible()
    }
  } else {
    await expect(ocrToggle).toBeDisabled()
    await expect(page.getByLabel('已安装语言包（可多选）')).toHaveCount(0)
  }
  expect(browserErrors).toEqual([])
})

test('Xiaohongshu preview shows parser diagnostics and candidate dimensions', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await page.route('**/api/v1/xiaohongshu/preview', async route => {
    const request = route.request()
    expect(request.postDataJSON()).toEqual({
      share_text: 'https://www.xiaohongshu.com/explore/66aabbccddeeff0011223344',
      resolve_metadata: true,
    })
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        kind: 'direct',
        normalized_url: 'https://www.xiaohongshu.com/explore/66aabbccddeeff0011223344',
        canonical_url: 'https://www.xiaohongshu.com/explore/66aabbccddeeff0011223344',
        note_id: '66aabbccddeeff0011223344',
        metadata_status: 'resolved',
        title: '公开页面候选',
        description: null,
        author: null,
        thumbnail_present: true,
        media_download_supported: false,
        parser_version: 'xhs-html-meta-v2',
        page_structure_status: 'partial',
        diagnostic_codes: ['XHS_MEDIA_DIMENSIONS_MISSING'],
        media_candidates: [{
          candidate_id: 'xhs-image-0123456789abcdef0123',
          position: 1,
          role: 'cover',
          width: 1080,
          height: null,
        }],
        warnings: ['部分图片候选没有声明完整尺寸。'],
      }),
    })
  })

  await page.goto('/')
  await page.getByLabel('分享内容').fill(
    'https://www.xiaohongshu.com/explore/66aabbccddeeff0011223344',
  )
  await page.getByLabel(/尝试读取页面标题/).check()
  await page.getByRole('button', { name: '解析分享链接' }).click()

  await expect(page.getByRole('heading', { name: '公开页面候选' })).toBeVisible()
  await expect(page.getByText('xhs-html-meta-v2')).toBeVisible()
  await expect(page.getByText('部分匹配')).toBeVisible()
  await expect(page.getByText(/宽 1080 px · 高度未声明/)).toBeVisible()
  await expect(page.getByText('XHS_MEDIA_DIMENSIONS_MISSING')).toBeVisible()
  await expect(page.getByText(/xhscdn|token=/)).toHaveCount(0)
  expect(browserErrors).toEqual([])
})

test('DOCX watermark workflow reaches verified result and report', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await upload(page, 'browser-watermark.docx')

  await page.getByLabel('目标文字（可选）').fill('DRAFT')
  await page.getByRole('button', { name: '开始扫描' }).click()
  await expect(page.getByRole('heading', { name: 'DRAFT', exact: true })).toBeVisible()
  await expect(page.getByText('与目标匹配', { exact: true })).toBeVisible()
  await expect(page.getByText('需要复核', { exact: true })).toBeVisible()
  await expect(page.getByAltText(/候选预览/)).toBeVisible()
  await page.getByLabel('选择此候选').nth(1).check()
  await page.getByLabel(/我已核对该对象/).check()
  await page.getByRole('button', { name: /生成无水印副本/ }).click()

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('docx')
  expect(report.processing.kind).toBe('object_removal')
  expect(report.processing.selected_target_count).toBe(2)
  await expectResultDownload(page, /-cleaned\.docx$/)
  expect(browserErrors).toEqual([])
})

test('CodeCV scan protects signed input and produces a privacy-safe report', async ({ page }) => {
  const browserErrors = watchBrowserErrors(page)
  await upload(page, 'browser-codecv.pdf')

  await page.getByRole('button', { name: '扫描 CodeCV 结构' }).click()
  await expect(page.getByRole('heading', { name: 'CodeCV 结构匹配统计' })).toBeVisible()
  const diagnostics = page.locator('.codecv-diagnostics')
  await expect(diagnostics).toContainText('扫描页数1')
  await expect(diagnostics).toContainText('含 Pattern 的页面1')
  await expect(diagnostics).toContainText('完整操作签名1')
  await expect(diagnostics).toContainText('已确认 / 待复核1 / 0')
  await expect(diagnostics).toContainText('codecv-pattern-fill-v1')
  await expect(diagnostics).not.toContainText('browser-codecv.pdf')
  await expect(diagnostics).not.toContainText('/Watermark1')

  await page.getByRole('button', { name: '复制诊断' }).click()
  await expect(page.getByText(/已复制脱敏诊断|浏览器未允许复制/)).toBeVisible()
  await page.getByLabel('选择此候选').check()
  const signatureConfirmation = page.getByLabel(
    /现有数字签名将在 CodeCV 清理副本中失效/,
  )
  await expect(signatureConfirmation).toBeVisible()
  const processButton = page.getByRole('button', { name: /生成无水印 PDF副本/ })
  await expect(processButton).toBeDisabled()
  await signatureConfirmation.check()
  await processButton.click()

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('pdf')
  expect(report.processing.kind).toBe('object_removal')
  expect(report.processing.warning_codes).toContain('PDF_DIGITAL_SIGNATURE_INVALIDATION')
  await expectResultDownload(page, /-cleaned\.pdf$/)
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
  await page.getByRole('button', { name: '加入计划草稿' }).click()
  await page.locator('#pdf-redaction-page').selectOption('2')
  await page.getByRole('button', { name: '加入计划草稿' }).click()
  await expect(page.getByRole('heading', { name: '2 个区域 · 2 页' })).toBeVisible()
  await page.getByRole('button', { name: '检查 2 个区域的重叠风险' }).click()

  const overlapConfirmation = page.getByLabel(/我已核对相交对象/)
  await expect(overlapConfirmation).toBeVisible()
  await overlapConfirmation.check()
  const signatureConfirmation = page.getByLabel(/现有数字签名将在新副本中失效/)
  await expect(signatureConfirmation).toBeVisible()
  await expect(page.getByRole('button', { name: '生成区域删除后的 PDF 副本' })).toBeDisabled()
  await signatureConfirmation.check()
  await page.getByRole('button', { name: '生成区域删除后的 PDF 副本' }).click()

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('pdf')
  expect(report.processing.kind).toBe('pdf_redaction')
  expect(report.processing.selected_target_count).toBe(2)
  expect(report.processing.warning_codes).toContain('PDF_REDACTION_OVERLAP')
  expect(report.processing.warning_codes).toContain('PDF_DIGITAL_SIGNATURE_INVALIDATION')
  await expectResultDownload(page, /-cleaned\.pdf$/)
  expect(browserErrors).toEqual([])
})

test('image editor keeps source coordinates after zoom and pan', async ({ page }) => {
  await upload(page, 'browser-watermark.png')
  await page.getByRole('button', { name: '检查图片并编辑蒙版' }).click()
  const image = page.locator('.image-mask-canvas img')
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).complete)).toBe(true)
  await image.scrollIntoViewIfNeeded()
  const viewport = page.getByLabel('可缩放图片视口')
  await expect(page.getByLabel('当前缩放比例')).toHaveText('100%')
  await page.getByRole('button', { name: '放大图片' }).click()
  await page.getByRole('button', { name: '放大图片' }).click()
  await expect(page.getByLabel('当前缩放比例')).toHaveText('200%')
  await page.getByRole('button', { name: '平移', exact: true }).click()
  await expect(page.getByRole('button', { name: '平移', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await viewport.scrollIntoViewIfNeeded()
  let viewportBounds = await viewport.boundingBox()
  expect(viewportBounds).not.toBeNull()
  if (!viewportBounds) throw new Error('Image viewport has no layout bounds.')
  const scrollBeforePan = await viewport.evaluate(element => ({
    left: element.scrollLeft,
    top: element.scrollTop,
  }))
  await page.mouse.move(viewportBounds.x + viewportBounds.width * 0.65, viewportBounds.y + viewportBounds.height * 0.65)
  await page.mouse.down()
  await page.mouse.move(viewportBounds.x + viewportBounds.width * 0.4, viewportBounds.y + viewportBounds.height * 0.4)
  await page.mouse.up()
  const scrollAfterPan = await viewport.evaluate(element => ({
    left: element.scrollLeft,
    top: element.scrollTop,
  }))
  expect(scrollAfterPan.left).toBeGreaterThan(scrollBeforePan.left)
  expect(scrollAfterPan.top).toBeGreaterThan(scrollBeforePan.top)

  await page.getByRole('button', { name: '矩形', exact: true }).click()
  await viewport.scrollIntoViewIfNeeded()
  viewportBounds = await viewport.boundingBox()
  expect(viewportBounds).not.toBeNull()
  if (!viewportBounds) throw new Error('Image viewport has no layout bounds after selecting rectangle.')
  let bounds = await image.boundingBox()
  expect(bounds).not.toBeNull()
  if (!bounds) throw new Error('Image editor has no layout bounds.')
  const naturalSize = await image.evaluate(element => ({
    width: (element as HTMLImageElement).naturalWidth,
    height: (element as HTMLImageElement).naturalHeight,
  }))
  const selection = {
    x0: viewportBounds.x + viewportBounds.width * 0.28,
    y0: viewportBounds.y + viewportBounds.height * 0.28,
    x1: viewportBounds.x + viewportBounds.width * 0.56,
    y1: viewportBounds.y + viewportBounds.height * 0.56,
  }
  const expectedRegion = {
    x0: (selection.x0 - bounds.x) / bounds.width * naturalSize.width,
    y0: (selection.y0 - bounds.y) / bounds.height * naturalSize.height,
    x1: (selection.x1 - bounds.x) / bounds.width * naturalSize.width,
    y1: (selection.y1 - bounds.y) / bounds.height * naturalSize.height,
  }
  await page.mouse.move(selection.x0, selection.y0)
  await page.mouse.down()
  await page.mouse.move(selection.x1, selection.y1)
  await page.mouse.up()

  const firstRegion = page.getByText(/区域 1：/)
  await expect(firstRegion).toBeVisible()
  const coordinates = (await firstRegion.innerText()).match(/[\d.]+/g)?.map(Number)
  expect(coordinates).toHaveLength(5)
  expect(coordinates?.[1]).toBeCloseTo(expectedRegion.x0, 0)
  expect(coordinates?.[2]).toBeCloseTo(expectedRegion.y0, 0)
  expect(coordinates?.[3]).toBeCloseTo(expectedRegion.x1, 0)
  expect(coordinates?.[4]).toBeCloseTo(expectedRegion.y1, 0)
  const coordinatesBeforeReset = await firstRegion.innerText()
  await page.getByRole('button', { name: '复位视图' }).click()
  await expect(page.getByLabel('当前缩放比例')).toHaveText('100%')
  await expect(page.getByRole('button', { name: '平移', exact: true })).toBeDisabled()
  await expect(firstRegion).toHaveText(coordinatesBeforeReset)
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
  await page.getByRole('button', { name: '隐藏蒙版' }).click()
  await expect(page.locator('.image-mask-region')).toHaveCount(0)
  await page.getByRole('button', { name: '显示蒙版' }).click()

  await page.getByRole('button', { name: '多边形', exact: true }).click()
  await page.mouse.click(bounds.x + bounds.width * 0.58, bounds.y + bounds.height * 0.65)
  await page.mouse.click(bounds.x + bounds.width * 0.72, bounds.y + bounds.height * 0.62)
  await page.mouse.click(bounds.x + bounds.width * 0.66, bounds.y + bounds.height * 0.78)
  await page.getByRole('button', { name: '完成多边形' }).click()
  await expect(page.getByRole('heading', { name: '多边形蒙版 · 1' })).toBeVisible()
  await expect(page.locator('.image-mask-polygon').first()).toBeVisible()

  await page.getByRole('button', { name: '编辑顶点', exact: true }).click()
  const firstVertex = page.getByRole('button', { name: '多边形 1 顶点 1', exact: true })
  await expect(firstVertex).toBeVisible()
  const initialX = Number(await firstVertex.getAttribute('cx'))
  await firstVertex.press('ArrowRight')
  await expect.poll(async () => Number(await firstVertex.getAttribute('cx'))).toBe(initialX + 1)
  await page.getByRole('button', { name: '撤销', exact: true }).click()
  await expect.poll(async () => Number(await firstVertex.getAttribute('cx'))).toBe(initialX)
  await page.getByRole('button', { name: '重做', exact: true }).click()
  const vertexBounds = await firstVertex.boundingBox()
  expect(vertexBounds).not.toBeNull()
  if (!vertexBounds) throw new Error('Polygon vertex has no layout bounds.')
  await page.mouse.move(vertexBounds.x + vertexBounds.width / 2, vertexBounds.y + vertexBounds.height / 2)
  await page.mouse.down()
  await page.mouse.move(vertexBounds.x + vertexBounds.width / 2 + 12, vertexBounds.y + vertexBounds.height / 2 + 8)
  await page.mouse.up()
  await expect.poll(async () => Number(await firstVertex.getAttribute('cx'))).toBeGreaterThan(initialX + 1)

  await page.getByRole('button', { name: '画笔', exact: true }).click()
  await page.mouse.move(bounds.x + bounds.width * 0.72, bounds.y + bounds.height * 0.3)
  await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width * 0.86, bounds.y + bounds.height * 0.42)
  await page.mouse.up()
  await expect(page.getByRole('heading', { name: /修复蒙版 · [2-9]/ })).toBeVisible()

  await page.getByRole('button', { name: '橡皮', exact: true }).click()
  await page.mouse.move(bounds.x + bounds.width * 0.72, bounds.y + bounds.height * 0.3)
  await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width * 0.86, bounds.y + bounds.height * 0.42)
  await page.mouse.up()
  await expect(page.getByRole('heading', { name: '修复蒙版 · 1' })).toBeVisible()

  await page.getByRole('button', { name: '保护区', exact: true }).click()
  await page.mouse.click(bounds.x + bounds.width * 0.4, bounds.y + bounds.height * 0.45)
  await expect(page.getByRole('heading', { name: '保护区 · 1' })).toBeVisible()
  await page.getByRole('button', { name: '隐藏保护区' }).click()
  await expect(page.locator('.image-protected-region')).toHaveCount(0)
  await page.getByRole('button', { name: '显示保护区' }).click()

  await page.getByRole('button', { name: '撤销', exact: true }).click()
  await expect(page.getByRole('heading', { name: '保护区 · 1' })).toHaveCount(0)
  await page.getByRole('button', { name: '重做', exact: true }).click()
  await expect(page.getByRole('heading', { name: '保护区 · 1' })).toBeVisible()
  await page.getByRole('button', { name: '验证蒙版草稿（1 个矩形，1 个多边形，1 个保护区）' }).click()
  await expect(page.getByRole('heading', { name: /背景复杂度/ })).toBeVisible()
  await expect(page.getByText('下一步建议', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '比较修复半径效果' }).click()
  const radiusPreviewPanel = page.getByRole('region', { name: '修复半径效果对比' })
  await expect(radiusPreviewPanel).toBeVisible()
  await expect(radiusPreviewPanel.getByRole('img')).toHaveCount(3)
  await radiusPreviewPanel.getByRole('button', { name: '选用修复半径 7' }).click()
  await expect(page.getByRole('spinbutton', { name: '修复半径', exact: true })).toHaveValue('7')
  const processImageButton = page.getByRole('button', { name: '使用 OpenCV 生成修复副本' })
  await processImageButton.click()
  const imageRiskConfirmations = page.locator('.image-mask-panel .risk-confirm input')
  await page.waitForTimeout(100)
  if (await imageRiskConfirmations.count()) {
    for (const confirmation of await imageRiskConfirmations.all()) await confirmation.check()
    await processImageButton.click()
  }

  await expectCompleted(page)
  const report = await downloadReport(page)
  expect(report.input.kind).toBe('png')
  expect(report.processing.kind).toBe('image_inpaint')
  expect(report.processing.selected_target_count).toBe(2)
  expect(report.processing.radius).toBe(7)
  expect(report.processing.protected_target_count).toBe(1)
  expect(report.processing.engine).toBe('opencv_telea')
  expect(report.processing.image_mask.rectangle_count).toBe(1)
  expect(report.processing.image_mask.polygon_count).toBe(1)
  expect(report.processing.image_mask.protected_region_count).toBe(1)
  expect(report.processing.image_mask.effective_masked_pixels).toBeGreaterThan(0)
  expect(report.processing.image_mask.coverage_ratio).toBeGreaterThan(0)
  expect(report.processing.image_pixel_validation.output_format).toBe('PNG')
  expect(report.processing.image_pixel_validation.outside_mask_changed_pixels).toBe(0)
  expect(report.processing.image_pixel_validation.dimensions_match).toBe(true)
  expect(report.processing.image_pixel_validation.outside_mask_unchanged).toBe(true)
  expect(report.processing.image_metadata_removal.policy).toBe('fresh_png_without_metadata')
  expect(report.processing.image_metadata_removal.output_exif_present).toBe(false)
  expect(report.processing.image_metadata_removal.output_icc_profile_present).toBe(false)
  expect(report.processing.image_metadata_removal.verified_clean).toBe(true)
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
  await expect(page.getByRole('progressbar', { name: '任务进度' })).toHaveAttribute(
    'aria-valuenow',
    '100',
  )
  await expect(page.getByText('已完成', { exact: true })).toBeVisible()
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
