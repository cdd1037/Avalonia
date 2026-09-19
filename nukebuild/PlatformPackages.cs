using System;
using Nuke.Common;
using Nuke.Common.IO;
using Nuke.Common.Tools.DotNet;
using static Nuke.Common.Tools.DotNet.DotNetTasks;

partial class Build
{
    [Parameter("Desktop platform to package: win, linux or osx")]
    public string PackagePlatform { get; set; }

    Target BuildPlatformPackages => _ => _
        .Requires(() => PackagePlatform)
        .Executes(() =>
        {
            if (PackagePlatform is not ("win" or "linux" or "osx"))
                throw new ArgumentException("PackagePlatform must be win, linux or osx.");

            Parameters.NugetIntermediateRoot.CreateOrCleanDirectory();
            DotNetPack(c => ApplySetting(c)
                .SetProject(RootDirectory / "build" / "PlatformPackages.proj")
                .AddProperty("AvaloniaPackagePlatform", PackagePlatform)
                .AddProperty("IncludeLinuxSkia", "false")
                .AddProperty("IncludeWasmSkia", "false"));

            BuildTasksPatcher.PatchBuildTasksInPackage(
                Parameters.NugetIntermediateRoot / $"Avalonia.Build.Tasks.{Parameters.Version}.nupkg", IlRepackTool);
            var config = Numerge.MergeConfiguration.LoadFile(RootDirectory / "nukebuild" / "numerge.json");
            // The Windows merge input does not exist on other platforms.
            if (PackagePlatform != "win")
                config.Packages.RemoveAll(p => p.Id == "Avalonia.Win32");
            Parameters.NugetRoot.CreateOrCleanDirectory();
            if (!Numerge.NugetPackageMerger.Merge(Parameters.NugetIntermediateRoot,
                    Parameters.NugetRoot, config, new NumergeNukeLogger()))
                throw new Exception("Platform package merge failed.");
            RefAssemblyGenerator.GenerateRefAsmsInPackage(
                Parameters.NugetRoot / $"Avalonia.{Parameters.Version}.nupkg",
                Parameters.NugetRoot / $"Avalonia.{Parameters.Version}.snupkg");
        });
}
