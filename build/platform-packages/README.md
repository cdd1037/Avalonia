# 按目标平台分发 Avalonia

此构建从本仓库源码生成桌面版 Avalonia，并把 NuGet **下载边界**设为单个 RID。
普通包不含 PDB；应用自己的 PDB 不受影响。当前覆盖 Windows x64/x86/arm64、
Linux glibc x64/arm64、macOS x64/arm64，提供 net8.0 与 net10.0 程序集。
不覆盖 Android、iOS、Browser、WinUI、Linux musl 或一次还原多个 RID。

## 使用

从成功的 `Platform NuGet packages` Actions 下载并解压平台 artifacts，
在 `NuGet.Config` 中加入该目录作为本地源。首次使用前配置好源：SDK 本身也需要还原。
Actions 只生成 artifacts，不发布 NuGet。未来发布时仍使用独立的 `Cdd.*` 包名；
这些名称尚未在公共源注册或验证所有权。

在应用旁的 `global.json` 中指定 artifact 对应的 SDK 版本：

```json
{
  "msbuild-sdks": {
    "Cdd.Avalonia.Sdk": "12.2.999-platform.RUN"
  }
}
```

应用项目改为：

```xml
<Project Sdk="Microsoft.NET.Sdk;Cdd.Avalonia.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <AvaloniaPackage Include="Avalonia.Themes.Fluent;Avalonia.Fonts.Inter" />
  </ItemGroup>
</Project>
```

SDK 默认引入 `Avalonia.Desktop`，其他组件通过 `AvaloniaPackage` 添加。
不要同时引用官方 `Avalonia.*` / `SkiaSharp` / `HarfBuzzSharp` 包：它们具有不同
NuGet 标识，但程序集身份相同，且会重新引入官方的多平台依赖。依赖官方包的
第三方 Avalonia 控件需要单独适配，不能承诺直接替换所有现有项目。
项目使用集中版本管理时，在该应用项目设置 `ManagePackageVersionsCentrally=false`；
SDK 固定整个分发图的版本，不能混用不同构建批次。

```sh
dotnet build                         # 开发机的 OS / 当前 .NET 进程架构
dotnet publish -r linux-arm64        # 显式目标优先；需提供 Linux artifact
```

可在项目内设置 `RuntimeIdentifier`，也可用命令行 `-r`。
程序中继续使用 `UsePlatformDetect()`。平台包只编译并依赖对应桌面后端。
普通 NuGet `buildTransitive` 文件在第一次还原之前尚不可用，因此无法可靠地用它
动态注入平台依赖；这里使用在项目求值前解析的 MSBuild SDK。

## 构建与验证

Actions 分别在 Windows、Linux 和 macOS 上运行：

1. `BuildPlatformPackages` 打包桌面项目图，沿用 Avalonia 的构建任务合并、核心包合并与引用程序集生成。
2. `package.py` 重命名分发包及完整内部依赖，保留原始程序集身份与第三方许可证。
   从固定版本的官方 SkiaSharp/HarfBuzz/ANGLE 包选取目标 RID 的 native 文件；macOS universal dylib 使用 `lipo` 拆为单架构。
   这是第三方二进制的重新分发，不是重新编译 Skia。原有签名不适用于派生包，予以移除；原作者及许可元数据保留。
3. `verify.py` 在仓库外创建独立应用，每个 RID 使用空 NuGet 缓存，验证包内文件、实际还原图、构建和发布。
   开发机 RID 不传 `-r`，验证自动选择；其他 RID 显式指定。
4. 在三个构建宿主上执行原生 Skia 绘图、HarfBuzz 字形整形、编译 XAML 和桌面后端初始化。
   其他架构仅验证还原/编译/发布，不宣称做过原生执行。
5. 在 Linux 开发机上使用显式 RID 还原和发布 Windows/macOS 应用，验证目标平台优先于开发机。
   消费测试同时覆盖 net8.0 与 net10.0。

下载到构建机的上游包仍包含全部原生平台；缩减的是应用消费者的下载和输出。
每个平台 artifact 附带 `provenance-*.json`，记录上游版本、来源、SHA-256 和输出包体积。
符号不放入发布的普通包；目前没有提供第三方符号包自动分发。

本地复现（需要仓库要求的 .NET SDK、Python 3，以及 macOS 构建所需 Xcode）：

```sh
git submodule update --init --recursive
dotnet run --project nukebuild/_build.csproj -- BuildPlatformPackages --package-platform win --force-nuget-version 12.2.999-platform.local
python build/platform-packages/package.py --platform win --version 12.2.999-platform.local
python build/platform-packages/verify.py --feed artifacts/platform-nuget --platform win --host-rid win-x64 --version 12.2.999-platform.local
```

Linux 的验证命令需在可用 X11 会话中运行，CI 使用 `xvfb-run -a`。
同一 checkout 切换构建 OS 时需要清理旧构建产物；CI 各平台使用全新 checkout。
