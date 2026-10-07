# 小红书分享链接边界

## 当前能力

`POST /api/v1/xiaohongshu/preview` 接受一段分享文案或一个 HTTPS 链接，完成两层处理：

1. **本地解析**：提取唯一链接、校验精确域名和笔记路径、去掉输出地址中的查询参数，并返回笔记 ID。
2. **可选元数据预览**：显式启用后，跟随有限次受控跳转，只读取 HTML 中的标题、描述、作者、canonical 地址以及“是否声明缩略图”。

接口不会返回、代理或保存 `og:image` 的地址，也不会下载图片或视频。它不执行页面 JavaScript，不使用登录 Cookie，不绕过访问控制，不调用非公开下载接口。这个边界用于先识别用户提供的笔记，再决定是否由用户上传自己有权处理的本地图片。

官方 Deep Link 文档给出的笔记标识形式是 `xhsdiscover://item/<note_id>`。本项目的 Web 入口当前识别以下 HTTPS 形式：

- `https://www.xiaohongshu.com/explore/<note_id>`
- `https://www.xiaohongshu.com/discovery/item/<note_id>`
- `https://www.xiaohongshu.com/item/<note_id>`
- `https://xhslink.com/<path>`（兼容实际分享短链；这不是项目所依赖的官方公开 API 合同，格式可能变化）

自定义 `xhsdiscover://` Scheme 不交给后端网络访问。前端分享文案应包含 HTTPS 链接。

参考资料：

- [小红书官方 Deep Link 文档](https://pages.xiaohongshu.com/activity/deeplink)
- [小红书开放平台 iOS 分享与 Universal Links 文档](https://agora.xiaohongshu.com/doc/ios)
- [小红书小程序分享文档](https://miniapp.xiaohongshu.com/doc/DC835356)
- [小红书知识产权保护平台](https://ipp.xiaohongshu.com/)

## 安全约束

- 仅接受 `https`，拒绝用户信息、非 443 端口、IP 地址和相似后缀域名。
- 直链和每一次跳转都必须落在精确允许列表内。
- 生产传输层先解析 DNS，拒绝任一非公网结果，再把连接固定到已检查的 IP；TLS 仍按原始域名校验证书。
- 不使用系统 HTTP 代理，不自动携带 Cookie，也不把输入链接写入持久化存储。
- 元数据响应必须是 HTML，默认最多读取 512 KiB、等待 5 秒、跟随 3 次跳转。
- API 输出会移除查询参数，避免把分享令牌或跟踪参数回显给界面。

元数据网络读取默认关闭。按需启用：

```bash
WMRM_XHS_METADATA_ENABLED=true wmrm-api
```

可调整的本机配置：

- `WMRM_XHS_METADATA_TIMEOUT_SECONDS`：默认 `5`
- `WMRM_XHS_METADATA_MAX_BYTES`：默认 `524288`
- `WMRM_XHS_METADATA_MAX_REDIRECTS`：默认 `3`

## 响应语义

`metadata_status` 可能为：

- `not_requested`：只做了本地解析。
- `disabled`：请求了元数据，但本机没有启用网络读取。
- `resolved`：完成页面读取；字段仍可能为空。
- `unavailable`：远端状态、内容类型、跳转或网络条件不满足。

`media_download_supported` 固定为 `false`。后续若实现“小红书图片去水印”，第一条可执行路径仍是让用户上传有权处理的图片文件，复用现有图片蒙版、风险预检和 OpenCV 处理闭环。
