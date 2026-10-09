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
                    Console.WriteLine("Downloading the latest original TV no Tomo title from Nintendo's title server...");
                    using (NusClient nus = new NusClient())
                        nus.DownloadTitle(OriginalTitleId, string.Empty, downloadDirectory, StoreType.WAD);

                    string[] candidates = Directory.GetFiles(downloadDirectory, OriginalTitleId + "v*.wad");
                    if (candidates.Length == 0)
                        throw new FileNotFoundException(
                            "NUS completed without producing the expected TV no Tomo WAD. The title may no longer be offered by that server.");

                    PatchTitle(candidates.OrderBy(path => path, StringComparer.Ordinal).Last(), output, translationsPath);
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
        Console.WriteLine();
        Console.WriteLine("The NUS mode downloads a title to a temporary directory, patches it, then deletes the downloaded source.");
        Console.WriteLine("This localizes a starter set of UI messages and title metadata; guide-service replacement is not yet implemented.");
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

        if (!wad.TmdContents.Any(item => item.Index == 7))
            throw new InvalidDataException("The title has no expected content index 7 UI resource archive.");

        byte[] uiArchiveBytes = wad.GetContentByIndex(7);
        using U8 uiArchive = U8.Load(uiArchiveBytes);
        var patchedNames = new List<string>();
        int patchedMessages = 0;
        foreach (string name in new[]
        {
            "Setting.bmg", "Remocon.bmg", "NandError.bmg", "Savedata.bmg",
            "Support.bmg", "Tips.bmg", "TipsRemocon.bmg", "WifiError.bmg"
        })
        {
            int nodeIndex = uiArchive.GetNodeIndex(name);
            if (nodeIndex < 0) continue;
            byte[] original = uiArchive.Data[nodeIndex];
            byte[] translated = BmgTranslator.Translate(original, name, translations, out int changed);
            if (changed == 0) continue;
            uiArchive.ReplaceFile(nodeIndex, translated);
            patchedMessages += changed;
            patchedNames.Add($"{name} ({changed})");
        }

        if (patchedMessages == 0)
            throw new InvalidDataException(
                "No native UI strings were translated. The archive format or message indices may have changed.");

        byte[] patchedUi = uiArchive.ToByteArray();
        int contentPosition = Array.FindIndex(wad.TmdContents, item => item.Index == 7);
        ReplaceContent(wad, contentPosition, patchedUi);

        // Preserve the original executable, graphics/layouts, banner animation, sound and controls.
        // Only selected BMG messages and Wii Menu title metadata change in this preview.
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
            translatedResources = patchedNames,
            preservedNativeExecutable = true,
            warning = "This is a native-UI localization preview. Original TV no Tomo guide-service requests are not yet redirected to the US guide backend."
        }, new JsonSerializerOptions { WriteIndented = true }));
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
