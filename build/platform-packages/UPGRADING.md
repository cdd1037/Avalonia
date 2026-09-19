# 跟进官方 Avalonia 版本

## 原则

- 选择 AvaloniaUI/Avalonia 的明确稳定版 tag，不把开发分支的版本号改成稳定版号冒充稳定源码。
- 在升级分支完成源码、分包、消费端验证，合入 main 后再手动发布。
- 官方版本、发行版批次和已发布 NuGet 包相互独立；不覆盖旧包，不自动升级消费者。

## 获取官方版本

```powershell
# 每个新 clone 只需配置一次；已有 upstream 时先检查其 URL。
git remote add upstream https://github.com/AvaloniaUI/Avalonia.git
gh api repos/AvaloniaUI/Avalonia/releases/latest --jq '.tag_name'
# 将下面的 <tag> 替换为核对后的版本，不要原样执行。
git fetch --no-tags upstream tag <tag>
git switch -c upgrade/avalonia-<tag>
```

GitHub latest 是选版入口，仍需查看该 release 的变更说明、是否为预发布，以及本项目所需平台是否受支持。

## 更新源码

正常情况下，在基于上一稳定版的分支上合并新的官方 tag：

```powershell
git merge --no-ff <tag>
git submodule update --init --recursive
```

如果仓库历史包含比目标稳定版更新的开发快照，普通 merge 可能保留开发代码，甚至显示 already up to date。
此时应从目标 tag 建立干净分支，重新应用本发行版的改造，而不是直接合并或仅修改版本号。
对比目标 tag 与最终源码，确保差异仅为有意保留的发行版改造。
不要 force-push 改写已经发布的 main 历史。

主要维护点：

- `src/Avalonia.Desktop/`：按平台选择窗口后端。
- `build/PlatformPackages.proj`、`nukebuild/PlatformPackages.cs`：桌面构建图与上游合包工具。
- `build/platform-packages/package.py`：包依赖转换、原生资产筛选、SDK 与 README。
- `build/platform-packages/sdk/`：消费者还原策略。
- `build/platform-packages/verify.py`、`smoke/`：跨 RID/TFM 验证与真实原生执行。
- 两个 platform/NuGet 工作流及 `scripts/platform-release/prepare_release.py`。

升级时特别检查上游项目的新增、删除、重命名，NuGet 依赖和原生库版本，目标框架，XAML 编译器、合包工具，以及部署 API 的变化。
同时核对 README 中的框架、平台和迁移说明；不要为掩盖不兼容而增加静默回退。

## 版本生成

`version.py` 读取 `build/SharedVersion.props` 的 `Version`，附加 GitHub 构建批次：

- `12.1.2` → `12.1.2-platform.<run_number>`
- `13.0.0-preview.1` → `13.0.0-preview.1.platform.<run_number>`

所有平台及跨目标验证使用相同版本；重试同一构建不会换版本。
发布流程从被验证构建的完整提交 SHA 读取版本，不使用 main 当前版本，也不凭包文件自行推断版本。
因此 main 升级后仍可校验此前构建；artifact 必须尚未过期。
SDK README 在打包时自动填入实际版本。

本地查看版本：

```powershell
python build/platform-packages/version.py --run-number 1
```

## 验证与发布

1. 推送升级分支并发起 PR，运行 `Platform NuGet packages`。
2. 要求 Windows、Linux、macOS 原生消费验证及跨操作系统还原/发布全部通过。
3. 检查真实应用的 XAML、窗口、字体和交互；需要 AOT 时在目标 OS 单独发布验证，不能用普通构建代替。
4. 合入 main，使用成功且已经合入 main 的构建 ID 手动运行 `Publish platform packages to NuGet`。
5. 发布流程下载原始 artifacts，验证所有包及依赖闭包，获取短期 NuGet 凭证，最后上传 SDK。
6. 使用新包在独立应用中还原；消费者通过修改 `global.json` 中的 SDK 版本显式升级。

从 `12.2.999-platform.*` 切换到 `12.1.2-platform.*` 时，新发行版的数值版本更低。
不要为了让 NuGet 排序靠前而伪造官方基础版本；消费者应显式固定目标版本。

流程不会自动发布新 NuGet 版本，也不会自动修改其他项目的 `global.json`。
