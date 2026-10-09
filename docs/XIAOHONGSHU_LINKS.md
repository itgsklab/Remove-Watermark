# 小红书分享链接边界

## 当前能力

`POST /api/v1/xiaohongshu/preview` 接受一段分享文案或一个 HTTPS 链接，完成两层处理：

1. **本地解析**：提取唯一链接、校验精确域名和笔记路径、去掉输出地址中的查询参数，并返回笔记 ID。
2. **可选元数据预览**：显式启用后，跟随有限次受控跳转，读取 HTML 中的标题、描述、作者、canonical 地址以及公开图片元数据。
3. **可选图片导入**：只向前端返回不可逆候选编号；用户选择后，后端重新读取页面、确认候选仍存在，再从受限的小红书 CDN 下载图片并保存到本地资产库。第一张有效图片标记为封面，其余重复 `og:image` 条目标记为图集图片。

接口不会把 `og:image`、查询令牌或 CDN 地址返回浏览器或写入数据库。它只读取公开 HTML 元数据，不执行页面 JavaScript，不使用登录 Cookie，不绕过访问控制，不调用非公开下载接口，也不处理视频。当前导入的是页面公开声明的图片候选，不保证是原始全尺寸图片，也不保证页面始终提供完整图集。

2026 年 10 月的兼容性抽样从小红书官方 `sitemap.xml` 的四个笔记索引中各取三个页面，共 12 个公开页面。样本均返回多条 `og:image`，其中属于 `xhscdn.com` 的条目使用 HTTP 形式声明。解析器只在页面元数据入口把这类精确 CDN 域名地址升级为 HTTPS；实际网络请求、媒体跳转和导入仍只允许 HTTPS。样本地址、页面正文、查询参数和媒体文件均不进入仓库。

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
- 页面声明的媒体地址必须使用 HTTP(S)，且主机必须是 `xhscdn.com` 或其子域；HTTP 声明会在发起请求前升级为 HTTPS，不允许显式端口。每次媒体跳转仍只接受 HTTPS，并重新执行相同校验。
- 媒体下载同样先拒绝非公网 DNS 结果并固定到已检查 IP，只接受 JPEG、PNG 和 WebP；文件签名还会经过统一资产导入校验。

元数据网络读取默认关闭。按需启用：

```bash
WMRM_XHS_METADATA_ENABLED=true \
WMRM_XHS_MEDIA_IMPORT_ENABLED=true \
wmrm-api
```

可调整的本机配置：

- `WMRM_XHS_METADATA_TIMEOUT_SECONDS`：默认 `5`
- `WMRM_XHS_METADATA_MAX_BYTES`：默认 `524288`
- `WMRM_XHS_METADATA_MAX_REDIRECTS`：默认 `3`
- `WMRM_XHS_MEDIA_MAX_BYTES`：默认 `26214400`，并且不会超过全局上传上限

## 响应语义

`metadata_status` 可能为：

- `not_requested`：只做了本地解析。
- `disabled`：请求了元数据，但本机没有启用网络读取。
- `resolved`：完成页面读取；字段仍可能为空。
- `unavailable`：远端状态、内容类型、跳转或网络条件不满足。

`media_download_supported` 只有在页面读取和图片导入同时启用时才为 `true`。`media_candidates` 只包含候选编号、顺序和 `cover`/`gallery` 角色，不包含远端 URL。`POST /api/v1/xiaohongshu/import` 会重新解析同一分享内容并拒绝已消失或变化的候选；成功后返回普通 `AssetResponse`，可直接进入图片检查、风险预检和 OpenCV 处理闭环。
