# Cdd.Avalonia.Sdk

A RID-specific Avalonia desktop distribution for Windows, Linux, and macOS.

**This is an unofficial community distribution, not an official Avalonia NuGet package.** Avalonia is built from this repository's source. Native dependencies such as SkiaSharp and HarfBuzzSharp are repackaged from upstream prebuilt assets, not rebuilt from their native source code.

This README applies to version `@VERSION@`. This is a prerelease distribution; drop-in compatibility with official Avalonia 11 or other versions is not guaranteed.

## Why use this distribution?

- Restore packages for one target runtime identifier (RID), without downloading this distribution's runtime assets for other operating systems or architectures.
- Pin the distribution's dependencies through a single SDK version.
- Keep the familiar Avalonia application model, including `AppBuilder.Configure<T>().UsePlatformDetect()`.
- Distribution runtime packages do not include PDB files. Debug symbols for your own application are configured separately.

> `Cdd.Avalonia.Sdk` is an **MSBuild SDK**, not a regular component package. Do not install it using `dotnet add package Cdd.Avalonia.Sdk`.

## Quick start

Install the .NET 10 SDK, create an empty directory, and add the following three files. The example uses NuGet.org. If you already have a `NuGet.Config`, make sure its sources and package source mapping allow `Cdd.*` and their dependencies to be restored.

### 1. global.json

```json
{
  "msbuild-sdks": {
    "Cdd.Avalonia.Sdk": "@VERSION@"
  }
}
```

If a `global.json` already exists, merge the `msbuild-sdks` section into it while preserving your existing .NET SDK configuration.

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

The SDK automatically references the platform-specific `Avalonia.Desktop` package and its dependencies. Do not add it again. Use the original component name in `AvaloniaPackage`, without a `Cdd.` prefix, RID suffix, or version.

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
            var button = new Button { Content = "Click me" };
            button.Click += (_, _) => button.Content = $"Clicks: {++count}";
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

Run the application from that directory:

```shell
dotnet run
```

This is a complete minimal example without XAML files. Regular `.axaml` applications are also supported.

## Supported platforms

| Operating system | RuntimeIdentifier values |
| --- | --- |
| Windows | `win-x64`, `win-x86`, `win-arm64` |
| Linux (glibc) | `linux-x64`, `linux-arm64` |
| macOS | `osx-x64`, `osx-arm64` |

Managed assemblies target `net8.0` and `net10.0`. To use .NET 8, change the example's `TargetFramework` to `net8.0` and use the corresponding SDK.

When no RID is specified, the SDK uses the host .NET runtime's RID. This may differ from the machine's hardware architecture, for example when running under emulation. Specify the target explicitly when publishing:

```shell
dotnet publish -c Release -r win-x64
dotnet publish -c Release -r linux-x64
dotnet publish -c Release -r osx-arm64
```

These are separate target examples; run the command you need. Restore only one RID at a time. Do not list multiple targets in `RuntimeIdentifiers`. You can also set the singular property `<RuntimeIdentifier>win-x64</RuntimeIdentifier>` in the project.

The default is `SelfContained=false`, so a regular publication requires the corresponding .NET runtime on the target machine. To include the .NET runtime:

```shell
dotnet publish -c Release -r win-x64 --self-contained true
```

Publishing for another target does not make its executable runnable on the build machine. Linux system dependencies, including graphics and font libraries, must still be provided by the deployment environment. This distribution does not support musl/Alpine, Android, iOS, browsers, or `AvaloniaSingleProject`.

## Adding components

```xml
<ItemGroup>
  <AvaloniaPackage Include="Avalonia.Themes.Fluent" />
  <AvaloniaPackage Include="Avalonia.Fonts.Inter" />
</ItemGroup>
```

Common optional components:

| Component | Purpose |
| --- | --- |
| `Avalonia.Themes.Fluent` | Fluent theme |
| `Avalonia.Themes.Simple` | Simple theme, as an alternative to Fluent |
| `Avalonia.Fonts.Inter` | Inter fonts, used with `.WithInterFont()` |
| `Avalonia.Headless` | Headless testing APIs |

If you do not need Inter, remove both its component declaration and `.WithInterFont()`. The distribution selects the underlying windowing backend, Skia, and HarfBuzz dependencies automatically.

**Not every official Avalonia extension has a corresponding Cdd package.** Do not assume a package exists by changing its prefix. Third-party controls, test framework adapters, and diagnostic tools require a separate dependency compatibility check.

## Migrating an existing project

1. Pin the SDK version in `global.json`.
2. Change the application project's SDK to `Microsoft.NET.Sdk;Cdd.Avalonia.Sdk`.
3. Remove direct references to official `Avalonia.*`, `SkiaSharp`, and `HarfBuzzSharp` packages that duplicate the distribution. Declare optional components using `AvaloniaPackage` instead.
4. Keep your application code, XAML, and `UsePlatformDetect()`, then review API differences and rebuild.

NuGet treats official package IDs and `Cdd.*` IDs as separate packages; they do not replace each other automatically. Third-party libraries or shared projects that transitively reference official packages may introduce duplicate assemblies or incompatible dependencies. Their dependency graphs may need adaptation. The distribution intentionally retains `Avalonia.BuildServices`; do not forcibly exclude that dependency.

The SDK currently does not support Central Package Management. In a solution using `Directory.Packages.props`, set the following property in the application project:

```xml
<ManagePackageVersionsCentrally>false</ManagePackageVersionsCentrally>
```

Also provide explicit versions for that project's other regular `PackageReference` items. This setting does not resolve third-party libraries that mix official Avalonia packages with this distribution.

## Native AOT and publishing without PDB files

AOT is an application publishing option, not this SDK's default behavior. Add the following to your project's `PropertyGroup`:

```xml
<PublishAot>true</PublishAot>
<SelfContained>true</SelfContained>
<DebugType>none</DebugType>
<DebugSymbols>false</DebugSymbols>
<CopyOutputSymbolsToPublishDirectory>false</CopyOutputSymbolsToPublishDirectory>
```

Then publish on the target operating system. For example, on Windows x64:

```shell
dotnet publish -c Release -r win-x64 -o artifacts/native/win-x64
```

- Install the native toolchain required by Native AOT. The Windows example requires Visual Studio's Desktop development with C++ tools. See the [.NET Native AOT documentation](https://learn.microsoft.com/dotnet/core/deploying/native-aot/) for full prerequisites. Support for a RID in regular builds does not imply Native AOT support for that RID.
- Native AOT does not support cross-OS compilation. Ordinary cross-target publishing commands are not a cross-OS AOT build solution.
- AOT does not mean single-file deployment. Distribute the entire publish directory, including native libraries required by the target, such as Skia, HarfBuzz, and ANGLE. Do not copy only the executable.
- Your application and third-party libraries must still support trimming and AOT. Do not ignore the associated warnings.
- Disabling debug symbols does not remove PDB files left by previous builds. Clean old outputs or use a fresh publish directory.

If executable size matters more than runtime performance, optionally add `<OptimizationPreference>Size</OptimizationPreference>`. This may trade performance for size and does not shrink upstream prebuilt native libraries. See [Native AOT optimization guidance](https://learn.microsoft.com/dotnet/core/deploying/native-aot/optimizing).

## Upgrading and troubleshooting

**How do I upgrade?** Change the SDK version in `global.json`, then restore and rebuild. All `AvaloniaPackage` items automatically use that distribution version. Do not mix platform packages from different releases.

**The SDK cannot be resolved.** Check `global.json` in the project directory or its ancestors, the exact version, NuGet.org connectivity, and any enterprise package source mapping. These are prerelease versions with a `-platform.*` suffix.

**Why are assets for other platforms still downloaded?** This SDK controls only this distribution's dependencies. Check whether your project or third-party libraries separately reference official cross-platform packages or other native asset packages.

**The platform or architecture is wrong.** Pass `-r` explicitly and run the result on a matching operating system and architecture. Do not reuse outputs across RIDs without restoring for the new target.

**How do I report an issue?** Include the distribution version, target framework, RID, .NET SDK version, error logs, and a minimal reproduction project.

- [Source and build configuration](https://github.com/cdd1037/Avalonia)
- [Issue tracker](https://github.com/cdd1037/Avalonia/issues)
- [SDK package on NuGet](https://www.nuget.org/packages/Cdd.Avalonia.Sdk)

This SDK is licensed under MIT. Avalonia and bundled third-party components retain their respective licenses and notices; see the files in the corresponding packages.
