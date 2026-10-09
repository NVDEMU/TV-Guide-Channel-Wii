using System.Reflection;
using System.Security.Cryptography;
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
            if (args.Length < 2)
            {
                Console.Error.WriteLine("Usage: native-title-patcher <input.wad> <output.wad> [translation.json]");
                Console.Error.WriteLine("The input WAD must be a legally obtained TV no Tomo channel WAD.");
                return 2;
            }
            string input = Path.GetFullPath(args[0]);
            string output = Path.GetFullPath(args[1]);
            string translationsPath = args.Length > 2
                ? Path.GetFullPath(args[2])
                : Path.Combine(AppContext.BaseDirectory, "native-english-messages.json");
            if (!File.Exists(input)) throw new FileNotFoundException("Input WAD was not found.", input);
            if (!File.Exists(translationsPath)) throw new FileNotFoundException("Translation resource was not found.", translationsPath);

            var json = JsonDocument.Parse(File.ReadAllText(translationsPath));
            var translations = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var item in json.RootElement.EnumerateObject())
                translations[item.Name] = item.Value.GetString() ?? string.Empty;

            using WAD wad = WAD.Load(input);
            if (wad.NumOfContents < 8)
                throw new InvalidDataException("The supplied title does not contain the expected UI resource content.");

            int contentPosition = Array.FindIndex(wad.TmdContents, item => item.Index == 7);
            if (contentPosition < 0)
                throw new InvalidDataException("The title has no content index 7 UI resource archive.");

            byte[] uiArchiveBytes = wad.GetContentByIndex(7);
            U8 uiArchive = U8.Load(uiArchiveBytes);
            var patchedNames = new List<string>();
            int patchedMessages = 0;
            foreach (string name in new[] { "Setting.bmg", "Remocon.bmg", "NandError.bmg", "Savedata.bmg", "Support.bmg", "Tips.bmg", "TipsRemocon.bmg", "WifiError.bmg" })
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

            byte[] patchedUi = uiArchive.ToByteArray();
            ReplaceContent(wad, contentPosition, patchedUi);

            // Preserve the original application, layouts, textures, banner animation, sound, and controls.
            // Change only the title metadata and native message resources in this first localization preview.
            wad.ChannelTitles = EnglishTitles;
            wad.Region = Region.USA;
            wad.ChangeTitleID(LowerTitleID.Channel, NewUpperTitleId);
            wad.FakeSign = true;

            Directory.CreateDirectory(Path.GetDirectoryName(output)!);
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
                warning = "This is a native-UI localization preview. Original TV no Tomo guide-service requests are not yet redirected to the TVmaze/US guide backend."
            }, new JsonSerializerOptions { WriteIndented = true }));
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("ERROR: " + ex.Message);
            return 1;
        }
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
