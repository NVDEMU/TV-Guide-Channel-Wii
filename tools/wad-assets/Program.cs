using System;
using System.IO;
using libWiiSharp;

if (args.Length != 2)
{
    Console.Error.WriteLine("Usage: WadAssetExtractor <base.wad> <output-directory>");
    return 2;
}

string wadPath = Path.GetFullPath(args[0]);
string outputDirectory = Path.GetFullPath(args[1]);

if (!File.Exists(wadPath))
{
    Console.Error.WriteLine($"Base WAD does not exist: {wadPath}");
    return 2;
}

Directory.CreateDirectory(outputDirectory);

try
{
    using WAD wad = WAD.Load(wadPath);
    if (!wad.HasBanner)
    {
        Console.Error.WriteLine("The base WAD has no readable BannerApp.");
        return 3;
    }

    string[] names = wad.BannerApp.StringTable;
    byte[][] files = wad.BannerApp.Data;
    bool gotBanner = false;
    bool gotIcon = false;

    for (int i = 0; i < names.Length && i < files.Length; i++)
    {
        string name = names[i];
        if (name.Equals("banner.bin", StringComparison.OrdinalIgnoreCase))
        {
            File.WriteAllBytes(Path.Combine(outputDirectory, "banner.bin"), files[i]);
            gotBanner = true;
        }
        else if (name.Equals("icon.bin", StringComparison.OrdinalIgnoreCase))
        {
            File.WriteAllBytes(Path.Combine(outputDirectory, "icon.bin"), files[i]);
            gotIcon = true;
        }
    }

    if (!gotBanner || !gotIcon)
    {
        Console.Error.WriteLine(
            $"Could not find both banner.bin and icon.bin in the BannerApp (banner={gotBanner}, icon={gotIcon}).");
        return 4;
    }

    Console.WriteLine($"Extracted base banner/icon assets into: {outputDirectory}");
    Console.WriteLine("These are the base WAD's current images; the displayed channel title will be changed separately.");
    return 0;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Unable to read the WAD/banner assets: {ex.Message}");
    return 5;
}
