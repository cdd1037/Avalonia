using System.Globalization;
using Avalonia;
using Avalonia.Headless;
using Avalonia.Markup.Xaml;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using SkiaSharp;

namespace Smoke;

public class App : Application
{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);
}

internal static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        var builder = AppBuilder.Configure<App>().UsePlatformDetect().WithInterFont();
        if (!args.Contains("--desktop"))
            builder.UseHeadless(new AvaloniaHeadlessPlatformOptions { UseHeadlessDrawing = false });
        builder.SetupWithoutStarting();

        // Exercises compiled XAML, the theme, the Skia native ABI and HarfBuzz
        // text shaping using the shipped Inter font rather than runner fonts.
        using var bitmap = new RenderTargetBitmap(new PixelSize(240, 80), new Vector(96, 96));
        using (var drawing = bitmap.CreateDrawingContext())
        {
            drawing.FillRectangle(Brushes.White, new Rect(0, 0, 240, 80));
            var text = new FormattedText("Avalonia ffi 123", CultureInfo.InvariantCulture,
                FlowDirection.LeftToRight, new Typeface("avares://Avalonia.Fonts.Inter/Assets#Inter"),
                24, Brushes.Black);
            if (text.Width <= 0)
                throw new InvalidOperationException("Text shaping produced no glyphs.");
            drawing.DrawText(text, new Point(10, 10));
        }
        using var stream = new MemoryStream();
        bitmap.Save(stream);
        using var decoded = SKBitmap.Decode(stream.ToArray());
        if (decoded.Width != 240 || !decoded.Pixels.Any(p => p.Red < 128))
            throw new InvalidOperationException("Native rendering did not produce text pixels.");

        var references = typeof(AppBuilderDesktopExtensions).Assembly.GetReferencedAssemblies()
            .Select(a => a.Name).ToHashSet();
        var expected = OperatingSystem.IsWindows() ? "Avalonia.Win32" :
            OperatingSystem.IsMacOS() ? "Avalonia.Native" : "Avalonia.X11";
        foreach (var backend in new[] { "Avalonia.Win32", "Avalonia.Native", "Avalonia.X11" })
            if (references.Contains(backend) != (backend == expected))
                throw new InvalidOperationException($"Incorrect desktop reference: {backend}");
        Console.WriteLine($"PASS: {expected}; compiled XAML, native Skia rendering and HarfBuzz shaping.");
    }
}
