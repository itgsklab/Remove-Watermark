# Third-party dependency inventory

This file is generated from the pinned Python packaging constraints and npm lockfile.
It records release inputs; it is not a legal opinion or a substitute for license review.
Regenerate it with `make release-metadata` and verify it with `make release-metadata-check`.

- Input digest: `34bde146ef9f0594a0654d6c2f05301dcd50e3e73498d22fee6f44fd8f979201`
- Python packages: 34
- npm packages: 126
- Vendored components: 1
- License fields: `NOASSERTION` until an authoritative package-by-package review is recorded

| Ecosystem | Package | Version | Usage | Direct | Platform condition |
| --- | --- | --- | --- | --- | --- |
| Python | `PyYAML` | `6.0.3` | locked transitive | no | — |
| Python | `SQLAlchemy` | `2.0.54` | runtime | yes | — |
| Python | `altgraph` | `0.17.5` | locked transitive | no | — |
| Python | `annotated-doc` | `0.0.5` | locked transitive | no | — |
| Python | `annotated-types` | `0.8.0` | locked transitive | no | — |
| Python | `anyio` | `4.15.1` | locked transitive | no | — |
| Python | `click` | `8.5.0` | locked transitive | no | — |
| Python | `defusedxml` | `0.7.1` | runtime | yes | — |
| Python | `fastapi` | `0.141.1` | runtime | yes | — |
| Python | `h11` | `0.16.0` | locked transitive | no | — |
| Python | `httptools` | `0.8.0` | locked transitive | no | — |
| Python | `idna` | `3.20` | locked transitive | no | — |
| Python | `macholib` | `1.16.4` | locked transitive | no | sys_platform == "darwin" |
| Python | `numpy` | `2.5.3` | runtime | yes | — |
| Python | `opencv-python-headless` | `5.0.0.93` | runtime | yes | — |
| Python | `packaging` | `26.3` | locked transitive | no | — |
| Python | `pefile` | `2024.8.26` | locked transitive | no | sys_platform == "win32" |
| Python | `pillow` | `12.3.0` | runtime | yes | — |
| Python | `pydantic` | `2.13.5` | locked transitive | no | — |
| Python | `pydantic-core` | `2.46.5` | locked transitive | no | — |
| Python | `pydantic-settings` | `2.15.0` | runtime | yes | — |
| Python | `pymupdf` | `1.28.2` | runtime | yes | — |
| Python | `pypdf` | `6.19.0` | runtime | yes | — |
| Python | `python-dotenv` | `1.2.3` | locked transitive | no | — |
| Python | `python-multipart` | `0.0.32` | runtime | yes | — |
| Python | `pywin32-ctypes` | `0.2.3` | locked transitive | no | sys_platform == "win32" |
| Python | `setuptools` | `84.0.0` | locked transitive | no | — |
| Python | `starlette` | `1.7.0` | locked transitive | no | — |
| Python | `typing-extensions` | `4.16.0` | locked transitive | no | — |
| Python | `typing-inspection` | `0.4.4` | locked transitive | no | — |
| Python | `uvicorn` | `0.53.0` | runtime | yes | — |
| Python | `uvloop` | `0.22.1` | locked transitive | no | sys_platform != "win32" |
| Python | `watchfiles` | `1.3.0` | locked transitive | no | — |
| Python | `websockets` | `17.1` | locked transitive | no | — |
| Vendored | `Microsoft-Florence-2-runtime` | `5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac` | optional runtime source | yes | — |
| npm | `@babel/helper-string-parser` | `7.29.7` | runtime | no | — |
| npm | `@babel/helper-validator-identifier` | `7.29.7` | runtime | no | — |
| npm | `@babel/parser` | `7.29.9` | runtime | no | — |
| npm | `@babel/types` | `7.29.8` | runtime | no | — |
| npm | `@esbuild/aix-ppc64` | `0.28.2` | development | no | os=aix; cpu=ppc64 |
| npm | `@esbuild/android-arm` | `0.28.2` | development | no | os=android; cpu=arm |
| npm | `@esbuild/android-arm64` | `0.28.2` | development | no | os=android; cpu=arm64 |
| npm | `@esbuild/android-x64` | `0.28.2` | development | no | os=android; cpu=x64 |
| npm | `@esbuild/darwin-arm64` | `0.28.2` | development | no | os=darwin; cpu=arm64 |
| npm | `@esbuild/darwin-x64` | `0.28.2` | development | no | os=darwin; cpu=x64 |
| npm | `@esbuild/freebsd-arm64` | `0.28.2` | development | no | os=freebsd; cpu=arm64 |
| npm | `@esbuild/freebsd-x64` | `0.28.2` | development | no | os=freebsd; cpu=x64 |
| npm | `@esbuild/linux-arm` | `0.28.2` | development | no | os=linux; cpu=arm |
| npm | `@esbuild/linux-arm64` | `0.28.2` | development | no | os=linux; cpu=arm64 |
| npm | `@esbuild/linux-ia32` | `0.28.2` | development | no | os=linux; cpu=ia32 |
| npm | `@esbuild/linux-loong64` | `0.28.2` | development | no | os=linux; cpu=loong64 |
| npm | `@esbuild/linux-mips64el` | `0.28.2` | development | no | os=linux; cpu=mips64el |
| npm | `@esbuild/linux-ppc64` | `0.28.2` | development | no | os=linux; cpu=ppc64 |
| npm | `@esbuild/linux-riscv64` | `0.28.2` | development | no | os=linux; cpu=riscv64 |
| npm | `@esbuild/linux-s390x` | `0.28.2` | development | no | os=linux; cpu=s390x |
| npm | `@esbuild/linux-x64` | `0.28.2` | development | no | os=linux; cpu=x64 |
| npm | `@esbuild/netbsd-arm64` | `0.28.2` | development | no | os=netbsd; cpu=arm64 |
| npm | `@esbuild/netbsd-x64` | `0.28.2` | development | no | os=netbsd; cpu=x64 |
| npm | `@esbuild/openbsd-arm64` | `0.28.2` | development | no | os=openbsd; cpu=arm64 |
| npm | `@esbuild/openbsd-x64` | `0.28.2` | development | no | os=openbsd; cpu=x64 |
| npm | `@esbuild/openharmony-arm64` | `0.28.2` | development | no | os=openharmony; cpu=arm64 |
| npm | `@esbuild/sunos-x64` | `0.28.2` | development | no | os=sunos; cpu=x64 |
| npm | `@esbuild/win32-arm64` | `0.28.2` | development | no | os=win32; cpu=arm64 |
| npm | `@esbuild/win32-ia32` | `0.28.2` | development | no | os=win32; cpu=ia32 |
| npm | `@esbuild/win32-x64` | `0.28.2` | development | no | os=win32; cpu=x64 |
| npm | `@jridgewell/sourcemap-codec` | `1.6.0` | runtime | no | — |
| npm | `@napi-rs/canvas` | `0.1.100` | optional runtime | no | — |
| npm | `@napi-rs/canvas-android-arm64` | `0.1.100` | optional runtime | no | os=android; cpu=arm64 |
| npm | `@napi-rs/canvas-darwin-arm64` | `0.1.100` | optional runtime | no | os=darwin; cpu=arm64 |
| npm | `@napi-rs/canvas-darwin-x64` | `0.1.100` | optional runtime | no | os=darwin; cpu=x64 |
| npm | `@napi-rs/canvas-linux-arm-gnueabihf` | `0.1.100` | optional runtime | no | os=linux; cpu=arm |
| npm | `@napi-rs/canvas-linux-arm64-gnu` | `0.1.100` | optional runtime | no | os=linux; cpu=arm64 |
| npm | `@napi-rs/canvas-linux-arm64-musl` | `0.1.100` | optional runtime | no | os=linux; cpu=arm64 |
| npm | `@napi-rs/canvas-linux-riscv64-gnu` | `0.1.100` | optional runtime | no | os=linux; cpu=riscv64 |
| npm | `@napi-rs/canvas-linux-x64-gnu` | `0.1.100` | optional runtime | no | os=linux; cpu=x64 |
| npm | `@napi-rs/canvas-linux-x64-musl` | `0.1.100` | optional runtime | no | os=linux; cpu=x64 |
| npm | `@napi-rs/canvas-win32-arm64-msvc` | `0.1.100` | optional runtime | no | os=win32; cpu=arm64 |
| npm | `@napi-rs/canvas-win32-x64-msvc` | `0.1.100` | optional runtime | no | os=win32; cpu=x64 |
| npm | `@napi-rs/lzma-linux-x64-gnu` | `1.5.1` | development | no | os=linux; cpu=x64 |
| npm | `@rolldown/pluginutils` | `1.0.1` | development | no | — |
| npm | `@rollup/rollup-android-arm-eabi` | `4.63.4` | development | no | os=android; cpu=arm |
| npm | `@rollup/rollup-android-arm64` | `4.63.4` | development | no | os=android; cpu=arm64 |
| npm | `@rollup/rollup-darwin-arm64` | `4.63.4` | development | no | os=darwin; cpu=arm64 |
| npm | `@rollup/rollup-darwin-x64` | `4.63.4` | development | no | os=darwin; cpu=x64 |
| npm | `@rollup/rollup-freebsd-arm64` | `4.63.4` | development | no | os=freebsd; cpu=arm64 |
| npm | `@rollup/rollup-freebsd-x64` | `4.63.4` | development | no | os=freebsd; cpu=x64 |
| npm | `@rollup/rollup-linux-arm-gnueabihf` | `4.63.4` | development | no | os=linux; cpu=arm |
| npm | `@rollup/rollup-linux-arm-musleabihf` | `4.63.4` | development | no | os=linux; cpu=arm |
| npm | `@rollup/rollup-linux-arm64-gnu` | `4.63.4` | development | no | os=linux; cpu=arm64 |
| npm | `@rollup/rollup-linux-arm64-musl` | `4.63.4` | development | no | os=linux; cpu=arm64 |
| npm | `@rollup/rollup-linux-loong64-gnu` | `4.63.4` | development | no | os=linux; cpu=loong64 |
| npm | `@rollup/rollup-linux-loong64-musl` | `4.63.4` | development | no | os=linux; cpu=loong64 |
| npm | `@rollup/rollup-linux-ppc64-gnu` | `4.63.4` | development | no | os=linux; cpu=ppc64 |
| npm | `@rollup/rollup-linux-ppc64-musl` | `4.63.4` | development | no | os=linux; cpu=ppc64 |
| npm | `@rollup/rollup-linux-riscv64-gnu` | `4.63.4` | development | no | os=linux; cpu=riscv64 |
| npm | `@rollup/rollup-linux-riscv64-musl` | `4.63.4` | development | no | os=linux; cpu=riscv64 |
| npm | `@rollup/rollup-linux-s390x-gnu` | `4.63.4` | development | no | os=linux; cpu=s390x |
| npm | `@rollup/rollup-linux-x64-gnu` | `4.63.4` | development | no | os=linux; cpu=x64 |
| npm | `@rollup/rollup-linux-x64-musl` | `4.63.4` | development | no | os=linux; cpu=x64 |
| npm | `@rollup/rollup-openbsd-x64` | `4.63.4` | development | no | os=openbsd; cpu=x64 |
| npm | `@rollup/rollup-openharmony-arm64` | `4.63.4` | development | no | os=openharmony; cpu=arm64 |
| npm | `@rollup/rollup-win32-arm64-msvc` | `4.63.4` | development | no | os=win32; cpu=arm64 |
| npm | `@rollup/rollup-win32-ia32-msvc` | `4.63.4` | development | no | os=win32; cpu=ia32 |
| npm | `@rollup/rollup-win32-x64-gnu` | `4.63.4` | development | no | os=win32; cpu=x64 |
| npm | `@rollup/rollup-win32-x64-msvc` | `4.63.4` | development | no | os=win32; cpu=x64 |
| npm | `@types/estree` | `1.0.9` | development | no | — |
| npm | `@types/node` | `24.13.6` | development | yes | — |
| npm | `@vitejs/plugin-vue` | `6.0.9` | development | yes | — |
| npm | `@volar/language-core` | `2.4.28` | development | no | — |
| npm | `@volar/source-map` | `2.4.28` | development | no | — |
| npm | `@volar/typescript` | `2.4.28` | development | no | — |
| npm | `@vue/compiler-core` | `3.5.43` | runtime | no | — |
| npm | `@vue/compiler-dom` | `3.5.43` | runtime | no | — |
| npm | `@vue/compiler-sfc` | `3.5.43` | runtime | no | — |
| npm | `@vue/compiler-ssr` | `3.5.43` | runtime | no | — |
| npm | `@vue/devtools-api` | `6.6.4` | runtime | no | — |
| npm | `@vue/devtools-api` | `7.7.10` | runtime | no | — |
| npm | `@vue/devtools-kit` | `7.7.10` | runtime | no | — |
| npm | `@vue/devtools-shared` | `7.7.10` | runtime | no | — |
| npm | `@vue/language-core` | `3.3.11` | development | no | — |
| npm | `@vue/reactivity` | `3.5.43` | runtime | no | — |
| npm | `@vue/runtime-core` | `3.5.43` | runtime | no | — |
| npm | `@vue/runtime-dom` | `3.5.43` | runtime | no | — |
| npm | `@vue/server-renderer` | `3.5.43` | runtime | no | — |
| npm | `@vue/shared` | `3.5.43` | runtime | no | — |
| npm | `@vue/tsconfig` | `0.8.1` | development | yes | — |
| npm | `alien-signals` | `3.2.1` | development | no | — |
| npm | `birpc` | `2.9.0` | runtime | no | — |
| npm | `copy-anything` | `4.1.1` | runtime | no | — |
| npm | `csstype` | `3.2.3` | runtime | no | — |
| npm | `entities` | `7.0.1` | runtime | no | — |
| npm | `esbuild` | `0.28.2` | development | no | — |
| npm | `estree-walker` | `2.0.2` | runtime | no | — |
| npm | `fdir` | `6.5.0` | development | no | — |
| npm | `fsevents` | `2.3.3` | development | no | os=darwin |
| npm | `hookable` | `5.5.3` | runtime | no | — |
| npm | `magic-string` | `0.30.21` | runtime | no | — |
| npm | `mitt` | `3.0.1` | runtime | no | — |
| npm | `muggle-string` | `0.4.1` | development | no | — |
| npm | `nanoid` | `3.3.19` | runtime | no | — |
| npm | `node-readable-to-web-readable-stream` | `0.4.2` | optional runtime | no | — |
| npm | `path-browserify` | `1.0.1` | development | no | — |
| npm | `pdfjs-dist` | `5.4.624` | runtime | yes | — |
| npm | `perfect-debounce` | `1.0.0` | runtime | no | — |
| npm | `picocolors` | `1.1.1` | runtime | no | — |
| npm | `picomatch` | `4.0.7` | development | no | — |
| npm | `pinia` | `3.0.4` | runtime | yes | — |
| npm | `postcss` | `8.5.28` | runtime | no | — |
| npm | `rfdc` | `1.4.1` | runtime | no | — |
| npm | `rollup` | `4.63.4` | development | no | — |
| npm | `source-map-js` | `1.2.2` | runtime | no | — |
| npm | `speakingurl` | `14.0.1` | runtime | no | — |
| npm | `superjson` | `2.2.6` | runtime | no | — |
| npm | `tinyglobby` | `0.2.17` | development | no | — |
| npm | `typescript` | `5.9.3` | runtime | yes | — |
| npm | `undici-types` | `7.18.2` | development | no | — |
| npm | `vite` | `7.3.6` | development | yes | — |
| npm | `vscode-uri` | `3.2.0` | development | no | — |
| npm | `vue` | `3.5.43` | runtime | yes | — |
| npm | `vue-router` | `4.6.4` | runtime | yes | — |
| npm | `vue-tsc` | `3.3.11` | development | yes | — |
