# Cdd.Avalonia.Sdk

按目标平台还原的 Avalonia 桌面发行版，支持 Windows、Linux 和 macOS。

**这是非官方社区发行版，不是 Avalonia 官方 NuGet 包。** Avalonia 从本仓库源码构建；SkiaSharp、HarfBuzzSharp 等原生依赖基于上游预编译资产重新打包，并非重新编译其原生源码。

本页对应版本：`@VERSION@`。这是预发布版本，不承诺与官方 Avalonia 11 或其他版本直接兼容。

## 为什么使用它

- 根据单个目标 RID 选择包，不必为一个桌面应用下载其他操作系统、架构的本发行版运行时资产。
- 用一个 SDK 版本固定整套发行版依赖，不必逐个维护平台包版本。
- 保留常规 Avalonia 编程方式，包括 `AppBuilder.Configure<T>().UsePlatformDetect()`。
- 本发行版普通运行时包不携带 PDB；应用自身的调试符号需要单独配置。

> `Cdd.Avalonia.Sdk` 是 **MSBuild SDK**，不是普通组件。不要使用 `dotnet add package Cdd.Avalonia.Sdk` 接入。

## 快速开始

安装 .NET 10 SDK，新建空目录，在其中创建以下三个文件。示例使用 NuGet.org；如果项目已有 `NuGet.Config`，请确保其包源和包源映射允许还原 `Cdd.*` 及其依赖。

### 1. global.json

```json
{
  "msbuild-sdks": {
    "Cdd.Avalonia.Sdk": "@VERSION@"
  }
}
```

如果已有 `global.json`，合并 `msbuild-sdks` 节点，保留已有的 .NET SDK 配置。

### 2. MyApp.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk;Cdd.Avalonia.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <AvaloniaPackage Include="Avalonia.Themes.Fluent" />
    <AvaloniaPackage Include="Avalonia.Fonts.Inter" />
  </ItemGroup>
</Project>
```

SDK 自动引入 `Avalonia.Desktop` 对应的平台包及其依赖，不需要再次声明。`AvaloniaPackage` 使用原组件名称，不加 `Cdd.` 前缀、RID 或版本。

### 3. Program.cs

```csharp
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Themes.Fluent;

internal static class Program
{
    [STAThread]
    public static int Main(string[] args) =>
        AppBuilder.Configure<DemoApp>()
            .UsePlatformDetect()
            .WithInterFont()
            .StartWithClassicDesktopLifetime(args);
}

public sealed class DemoApp : Application
{
    public override void Initialize() => Styles.Add(new FluentTheme());

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var count = 0;
            var button = new Button { Content = "点击我" };
            button.Click += (_, _) => button.Content = $"已点击 {++count} 次";
            desktop.MainWindow = new Window
            {
                Title = "Cdd Avalonia Demo",
                Width = 600,
                Height = 360,
                Content = new StackPanel
                {
                    Margin = new Thickness(24),
                    Spacing = 16,
                    Children =
                    {
                        new TextBlock { Text = "Hello, Avalonia!", FontSize = 28 },
                        button
                    }
                }
            };
        }
        base.OnFrameworkInitializationCompleted();
    }
}
```

在该目录运行：

```shell
dotnet run
```

这是不依赖 XAML 文件的完整最小示例；普通 `.axaml` 应用同样可以使用本发行版。

## 支持的平台

| 操作系统 | 可选 RuntimeIdentifier |
| --- | --- |
| Windows | `win-x64`、`win-x86`、`win-arm64` |
| Linux（glibc） | `linux-x64`、`linux-arm64` |
| macOS | `osx-x64`、`osx-arm64` |

托管程序集提供 `net8.0` 和 `net10.0` 目标。使用 .NET 8 时将示例的 `TargetFramework` 改为 `net8.0`，并使用相应 SDK。

未指定 RID 时，默认使用运行 .NET 的宿主运行时 RID；它可能与机器硬件架构不同，例如在模拟运行环境中。发布时建议显式指定：

```shell
dotnet publish -c Release -r win-x64
dotnet publish -c Release -r linux-x64
dotnet publish -c Release -r osx-arm64
```

以上是三个独立目标的示例，按需执行。每次仅还原一个 RID；不要用 `RuntimeIdentifiers` 一次列出多个目标。也可以在项目中设置单数属性 `<RuntimeIdentifier>win-x64</RuntimeIdentifier>`。

默认 `SelfContained=false`，普通发布需要目标机器安装对应 .NET 运行时。需要携带 .NET 运行时时使用：

```shell
dotnet publish -c Release -r win-x64 --self-contained true
```

跨目标普通发布不代表可以在当前机器运行目标程序。Linux 的系统图形、字体等依赖仍需由部署环境提供。本发行版不支持 musl/Alpine、Android、iOS、浏览器或 `AvaloniaSingleProject`。

## 添加组件

```xml
<ItemGroup>
  <AvaloniaPackage Include="Avalonia.Themes.Fluent" />
  <AvaloniaPackage Include="Avalonia.Fonts.Inter" />
</ItemGroup>
```

常用可选组件：

| 组件名称 | 用途 |
| --- | --- |
| `Avalonia.Themes.Fluent` | Fluent 主题 |
| `Avalonia.Themes.Simple` | Simple 主题，可代替 Fluent |
| `Avalonia.Fonts.Inter` | Inter 字体，配合 `.WithInterFont()` |
| `Avalonia.Headless` | 无窗口测试相关 API |

未使用 Inter 时，可以同时移除该组件声明和 `.WithInterFont()`。底层窗口后端、Skia 和 HarfBuzz 依赖由发行版选择，不必手工添加。

**并非所有官方 Avalonia 扩展包都有对应的 Cdd 包。** 不要仅通过替换包名前缀来猜测组件是否存在；例如第三方控件、测试框架适配包和诊断工具需要单独核对依赖。

## 从现有项目迁移

1. 在 `global.json` 固定本 SDK 的版本。
2. 将应用项目的 SDK 改为 `Microsoft.NET.Sdk;Cdd.Avalonia.Sdk`。
3. 移除与发行版重复的官方 `Avalonia.*`、`SkiaSharp`、`HarfBuzzSharp` 直接引用；可选组件改为上述 `AvaloniaPackage` 声明。
4. 保留应用代码、XAML 和 `UsePlatformDetect()`，然后检查 API 差异并重新构建。

NuGet 将官方包 ID 和 `Cdd.*` 视为不同包，不会自动相互替代。第三方库或共享项目若仍传递引用官方包，可能引入重复程序集或不兼容依赖，需要适配其依赖图。发行版有意保留的 `Avalonia.BuildServices` 依赖不属于这种重复引用，不要强行排除。

当前 SDK 不支持中央包版本管理。在使用 `Directory.Packages.props` 的解决方案中，应用项目需要设置：

```xml
<ManagePackageVersionsCentrally>false</ManagePackageVersionsCentrally>
```

同时为该项目其他普通 `PackageReference` 显式填写版本。此设置不会自动修复第三方库与官方 Avalonia 包的混用。

## Native AOT 与不生成 PDB

AOT 是应用的发布选项，不是本 SDK 的默认行为。在项目的 `PropertyGroup` 中添加：

```xml
<PublishAot>true</PublishAot>
<SelfContained>true</SelfContained>
<DebugType>none</DebugType>
<DebugSymbols>false</DebugSymbols>
<CopyOutputSymbolsToPublishDirectory>false</CopyOutputSymbolsToPublishDirectory>
```

然后在目标操作系统上发布，例如 Windows x64：

```shell
dotnet publish -c Release -r win-x64 -o artifacts/native/win-x64
```

- 需要安装 Native AOT 对应的本机编译工具链；Windows 示例需要 Visual Studio 的 C++ 桌面开发工具。完整要求见 [.NET Native AOT 文档](https://learn.microsoft.com/dotnet/core/deploying/native-aot/)。支持某个 RID 的普通构建，并不意味着该 RID 支持 Native AOT。
- Native AOT 不支持跨操作系统编译；不要把普通跨目标发布命令直接当成跨系统 AOT 构建方案。
- AOT 不等于单文件。请分发整个发布目录，包括 Skia、HarfBuzz、ANGLE 等目标平台需要的原生库，不要只复制 EXE。
- 应用及第三方库仍需满足裁剪和 AOT 要求；不要忽略相关警告。
- 关闭调试符号不会删除旧构建留下的 PDB。请清理旧输出或使用全新的发布目录验证。

如更重视可执行文件大小，可选添加 `<OptimizationPreference>Size</OptimizationPreference>`；它可能牺牲部分运行性能，不会缩小上游预编译原生库。见 [Native AOT 优化说明](https://learn.microsoft.com/dotnet/core/deploying/native-aot/optimizing)。

## 版本升级与常见问题

**如何升级？** 修改 `global.json` 中的 SDK 版本，再重新还原和构建。所有 `AvaloniaPackage` 自动采用相同发行版版本，不要混用不同批次的平台包。

**提示 SDK 无法解析？** 检查项目目录或祖先目录中的 `global.json`、版本拼写、NuGet.org 访问情况，以及企业包源映射。这里使用的是带 `-platform.*` 后缀的预发布版本。

**为什么仍下载了其他平台资产？** 本 SDK 只控制本发行版的依赖。检查项目及第三方库是否另行引用了官方跨平台包或其他原生资产包。

**平台或架构不正确？** 显式传入 `-r`，并确认目标程序运行在匹配的系统和架构上；不要跨 RID 复用未重新还原的输出。

**哪里反馈问题？** 请附上发行版版本、目标框架、RID、.NET SDK 版本、错误日志及最小复现项目。

- [源码与构建配置](https://github.com/cdd1037/Avalonia)
- [问题反馈](https://github.com/cdd1037/Avalonia/issues)
- [NuGet SDK 包](https://www.nuget.org/packages/Cdd.Avalonia.Sdk)

本 SDK 使用 MIT 许可证；Avalonia 和随包分发的第三方组件保留各自的许可证及声明，详见对应包中的文件。
