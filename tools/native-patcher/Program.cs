using System.Reflection;
using System.Text.Json;
using libWiiSharp;

namespace TvGuideNativePatcher;

internal static class Program
{
    private const string OriginalTitleId = "0001000148424e4a"; // Japanese TV no Tomo / HBNJ
    private const string NewUpperTitleId = "TVG1";
    private static readonly string[] EnglishTitles =
    {
        "TV Guide USA", "TV Guide USA", "TV Guide USA", "TV Guide USA",
        "TV Guide USA", "TV Guide USA", "TV Guide USA", "TV Guide USA"
    };

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 0 || args[0] is "-h" or "--help" or "help")
            {
                PrintUsage();
                return 0;
            }

            if (args[0] == "--self-test")
            {
                BmgTranslator.SelfTest();
                Console.WriteLine("BMG translator self-test passed.");
                return 0;
            }

            if (args[0] == "--download-latest")
            {
                if (args.Length < 2)
                {
                    PrintUsage();
                    return 2;
                }

                string output = Path.GetFullPath(args[1]);
                string translationsPath = args.Length > 2
                    ? Path.GetFullPath(args[2])
                    : Path.Combine(AppContext.BaseDirectory, "native-english-messages.json");
                string downloadDirectory = Path.Combine(Path.GetTempPath(), "tv-guide-native-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(downloadDirectory);
                try
                {
                    string originalWad = DownloadOriginalTitle(downloadDirectory);
                    PatchTitle(originalWad, output, translationsPath);
                    return 0;
                }
                finally
                {
                    try { Directory.Delete(downloadDirectory, recursive: true); }
                    catch (IOException) { /* Temporary input cleanup is best-effort. */ }
                    catch (UnauthorizedAccessException) { /* Temporary input cleanup is best-effort. */ }
                }
            }

            if (args.Length < 2)
            {
                PrintUsage();
                return 2;
            }

            string input = Path.GetFullPath(args[0]);
            string outputPath = Path.GetFullPath(args[1]);
            string translationPath = args.Length > 2
                ? Path.GetFullPath(args[2])
                : Path.Combine(AppContext.BaseDirectory, "native-english-messages.json");
            PatchTitle(input, outputPath, translationPath);
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("ERROR: " + ex.Message);
            return 1;
        }
    }

    private static void PrintUsage()
    {
        Console.WriteLine("Native TV no Tomo UI localization preview");
        Console.WriteLine("  native-title-patcher <input.wad> <output.wad> [translation.json]");
        Console.WriteLine("  native-title-patcher --download-latest <output.wad> [translation.json]");
        Console.WriteLine("  native-title-patcher --self-test");
        Console.WriteLine();
        Console.WriteLine("The NUS mode downloads a title to a temporary directory, patches it, then deletes the downloaded source.");
        Console.WriteLine("This localizes a starter set of UI messages and title metadata; guide-service replacement is not yet implemented.");
    }

    private static string DownloadOriginalTitle(string temporaryRoot)
    {
        string[] servers =
        {
            "https://ccs.shop.wii.com/ccs/download/",
            "https://ccs.cdn.c.shop.nintendowifi.net/ccs/download/",
            "https://nus.cdn.shop.wii.com/ccs/download/",
            "http://nus.cdn.shop.wii.com/ccs/download/"
        };
        var failures = new List<string>();
        foreach (string server in servers)
        {
            string directory = Path.Combine(temporaryRoot, Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            try
            {
                Console.WriteLine($"Trying original title server: {new Uri(server).Host}");
                using NusClient nus = new NusClient();
                nus.DownloadTitle(OriginalTitleId, string.Empty, directory, server, StoreType.WAD);
                string[] candidates = Directory.GetFiles(directory, OriginalTitleId + "v*.wad");
                if (candidates.Length > 0)
                    return candidates.OrderBy(path => path, StringComparer.Ordinal).Last();
                failures.Add($"{server}: no WAD output was written");
            }
            catch (Exception ex)
            {
                failures.Add($"{server}: {ex.GetType().Name}: {ex.Message}");
            }
        }
        throw new InvalidOperationException(
            "The original TV no Tomo title could not be downloaded from the checked NUS endpoints. " +
            "The service may have removed the title. Details: " + string.Join(" | ", failures));
    }

    private static void PatchTitle(string input, string output, string translationsPath)
    {
        input = Path.GetFullPath(input);
        output = Path.GetFullPath(output);
        translationsPath = Path.GetFullPath(translationsPath);
        if (!File.Exists(input)) throw new FileNotFoundException("Input WAD was not found.", input);
        if (!File.Exists(translationsPath)) throw new FileNotFoundException("Translation resource was not found.", translationsPath);

        using JsonDocument json = JsonDocument.Parse(File.ReadAllText(translationsPath));
        var translations = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (JsonProperty item in json.RootElement.EnumerateObject())
            translations[item.Name] = item.Value.GetString() ?? string.Empty;

        using WAD wad = WAD.Load(input);
        ulong expectedTitleId = Convert.ToUInt64(OriginalTitleId, 16);
        if (wad.TitleID != expectedTitleId)
            throw new InvalidDataException(
                $"Input title ID is {wad.TitleID:X16}; expected Japanese TV no Tomo {OriginalTitleId}.");

        var patchedNames = new List<string>();
        var discoveredBmgFiles = new List<string>();
        int patchedMessages = 0;
        int patchedArchives = 0;

        // Preserve and localize any banner-app text resources without changing its
        // original banner animation, layout or art. ChannelTitles below updates the
        // built-in Wii Menu title strings for every locale.
        U8 bannerApp = wad.BannerApp;
        int bannerTextChanges = PatchU8Archive(
            bannerApp, "banner-app", translations, patchedNames, discoveredBmgFiles, 0);
        if (bannerTextChanges > 0) patchedArchives++;
        patchedMessages += bannerTextChanges;

        // Scan every title content for U8 archives, not just one assumed index.
        // This finds main guide UI, settings, TV remote, errors, tips and support strings.
        foreach (var entry in wad.TmdContents.Where(item => item.Index != 0).ToArray())
        {
            byte[] bytes;
            try { bytes = wad.GetContentByIndex(entry.Index); }
            catch { continue; }

            if (!CanLoadU8(bytes)) continue;
            using U8 archive = U8.Load(bytes);
            int changed = PatchU8Archive(
                archive, $"{entry.Index:X4}", translations, patchedNames, discoveredBmgFiles, 0);
            if (changed == 0) continue;

            int contentPosition = Array.FindIndex(wad.TmdContents, item => item.Index == entry.Index);
            ReplaceContent(wad, contentPosition, archive.ToByteArray());
            patchedMessages += changed;
            patchedArchives++;
        }

        if (patchedMessages == 0)
            throw new InvalidDataException(
                "No native UI strings were translated. The supplied title's BMG files or translation indices may have changed.");

        // Preserve the original app, BRLYT/BRLAN layout and animation resources,
        // textures, sound, controls and native executable. Only supported message
        // tables and Wii Menu title metadata change in this preview.
        wad.ChannelTitles = EnglishTitles;
        wad.Region = Region.USA;
        wad.ChangeTitleID(LowerTitleID.Channel, NewUpperTitleId);
        wad.FakeSign = true;

        string? outputDirectory = Path.GetDirectoryName(output);
        if (!string.IsNullOrEmpty(outputDirectory)) Directory.CreateDirectory(outputDirectory);
        wad.Save(output);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            source = Path.GetFileName(input),
            output,
            originalTitleId = OriginalTitleId,
            newTitleId = "0001000154564731",
            region = "USA",
            translatedMessageCount = patchedMessages,
            patchedArchiveCount = patchedArchives,
            translatedResources = patchedNames,
            discoveredBmgResources = discoveredBmgFiles,
            localizedMenuTitleAllLanguages = true,
            preservedNativeExecutable = true,
            preservedOriginalBannerAnimationAndArtwork = true,
            warning = "This is a partial native-UI localization preview. Some Japanese messages may remain and original guide-service requests are not yet redirected to the US guide backend."
        }, new JsonSerializerOptions { WriteIndented = true }));
    }

    private static int PatchU8Archive(
        U8 archive,
        string archivePath,
        IReadOnlyDictionary<string, string> translations,
        List<string> patchedNames,
        List<string> discoveredBmgFiles,
        int depth)
    {
        if (depth > 4) return 0;
        int translatedCount = 0;
        string[] names = archive.StringTable;
        U8_Node[] nodes = archive.Nodes.ToArray();
        byte[][] data = archive.Data;

        for (int i = 0; i < Math.Min(Math.Min(names.Length, nodes.Length), data.Length); i++)
        {
            if (nodes[i].Type != U8_NodeType.File || data[i].Length == 0) continue;
            string resourcePath = $"{archivePath}/{names[i]}";
            byte[] file = data[i];

            if (BmgTranslator.IsBmg(file))
            {
                discoveredBmgFiles.Add(resourcePath);
                byte[] patched = BmgTranslator.Translate(file, resourcePath, translations, out int changed);
                if (changed > 0)
                {
                    archive.ReplaceFile(i, patched);
                    translatedCount += changed;
                    patchedNames.Add($"{resourcePath} ({changed})");
                }
                continue;
            }

            if (!CanLoadU8(file)) continue;
            try
            {
                using U8 nested = U8.Load(file);
                int nestedChanges = PatchU8Archive(
                    nested, resourcePath, translations, patchedNames, discoveredBmgFiles, depth + 1);
                if (nestedChanges > 0)
                {
                    archive.ReplaceFile(i, nested.ToByteArray());
                    translatedCount += nestedChanges;
                }
            }
            catch (Exception ex) when (ex is InvalidDataException or ArgumentException or IOException)
            {
                // Ignore archives that only resemble U8; preserve the original file.
            }
        }
        return translatedCount;
    }

    private static bool CanLoadU8(byte[] bytes)
    {
        try { return bytes.Length >= 0x20 && U8.IsU8(bytes); }
        catch { return false; }
    }

    private static void ReplaceContent(WAD wad, int tmdPosition, byte[] replacement)
    {
        FieldInfo field = typeof(WAD).GetField("contents", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException("Could not locate libWiiSharp's content list.");
        if (field.GetValue(wad) is not List<byte[]> contents)
            throw new InvalidDataException("libWiiSharp content list has an unexpected type.");
        if ((uint)tmdPosition >= (uint)contents.Count)
            throw new InvalidDataException("TMD/content array positions are inconsistent.");
        contents[tmdPosition] = replacement;
    }
}
