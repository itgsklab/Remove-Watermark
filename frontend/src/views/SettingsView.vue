<template>
  <section class="settings-head">
    <p class="eyebrow">本机设置</p>
    <h1>本地数据与服务</h1>
    <p class="intro">文件、任务记录和处理结果都保存在运行 FastAPI 的本机目录中。</p>
  </section>

  <section class="panel settings-panel">
    <div>
      <h2>Web 服务</h2>
      <p class="hint">页面与 API 由同一个本地服务提供。需要停止服务时，请回到启动它的终端并按 Ctrl+C。</p>
    </div>
  </section>

  <section class="panel settings-panel feedback-panel">
    <div>
      <p class="eyebrow">项目反馈</p>
      <h2>报告可复现的问题</h2>
      <p class="hint">GitHub 表单会引导你提供版本、运行环境、最小步骤和预期结果。</p>
    </div>
    <div class="feedback-actions">
      <a
        class="external-action primary-action"
        href="https://github.com/itgsklab/Remove-Watermark/issues/new/choose"
        target="_blank"
        rel="noopener noreferrer"
      >报告问题</a>
      <a
        class="external-action secondary-action"
        href="https://github.com/itgsklab/Remove-Watermark/issues"
        target="_blank"
        rel="noopener noreferrer"
      >查看现有问题</a>
    </div>
    <p class="privacy-note" role="note">
      请使用生成或彻底脱敏的最小样本。不要公开上传真实简历、合同、私人图片、凭据、有效分享链接、本地路径或其他个人信息。
    </p>
  </section>

  <section class="panel settings-panel security-panel">
    <div>
      <p class="eyebrow">安全与隐私</p>
      <h2>私密报告安全漏洞</h2>
      <p class="hint">涉及文件泄露、任意文件读写、SSRF、命令执行或绕过人工确认时，请使用 GitHub 私密漏洞报告，不要创建公开 Issue。</p>
    </div>
    <a
      class="external-action secondary-action"
      href="https://github.com/itgsklab/Remove-Watermark/security/advisories/new"
      target="_blank"
      rel="noopener noreferrer"
    >打开私密报告</a>
  </section>
</template>
