using System.Reflection;
using System.Text.Json;
using libWiiSharp;

namespace TvGuideNativePatcher;

internal static class Program
{
    private const string OriginalTitleId = "0001000148424e4a"; // Japanese TV no Tomo / HBNJ
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

            if (args[0] == "--audit-latest")
            {
                if (args.Length < 2) { PrintUsage(); return 2; }
                string reportPath = Path.GetFullPath(args[1]);
                string translationsPath = args.Length > 2
                    ? Path.GetFullPath(args[2])
                    : Path.Combine(AppContext.BaseDirectory, "native-english-messages.json");
                string downloadDirectory = Path.Combine(Path.GetTempPath(), "tv-guide-audit-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(downloadDirectory);
                try
                {
                    string originalWad = DownloadOriginalTitle(downloadDirectory);
                    WriteNativeAudit(originalWad, reportPath, translationsPath);
                    return 0;
                }
                finally
                {
                    try { Directory.Delete(downloadDirectory, recursive: true); }
                    catch (IOException) { }
                    catch (UnauthorizedAccessException) { }
                }
            }

            if (args[0] == "--audit")
            {
                if (args.Length < 3) { PrintUsage(); return 2; }
                string inputWad = Path.GetFullPath(args[1]);
                string reportPath = Path.GetFullPath(args[2]);
                string translationsPath = args.Length > 3
                    ? Path.GetFullPath(args[3])
                    : Path.Combine(AppContext.BaseDirectory, "native-english-messages.json");
                WriteNativeAudit(inputWad, reportPath, translationsPath);
                return 0;
            }

            if (args[0] == "--download-diagnostics")
            {
                if (args.Length < 3) { PrintUsage(); return 2; }
                string fullOutput = Path.GetFullPath(args[1]);
                string metadataOutput = Path.GetFullPath(args[2]);
                string translationsPath = args.Length > 3
                    ? Path.GetFullPath(args[3])
                    : Path.Combine(AppContext.BaseDirectory, "native-english-messages.json");
                string downloadDirectory = Path.Combine(Path.GetTempPath(), "tv-guide-diagnostic-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(downloadDirectory);
                try
                {
                    string originalWad = DownloadOriginalTitle(downloadDirectory);
                    PatchTitle(originalWad, metadataOutput, translationsPath, translateMessages: false);
                    PatchTitle(originalWad, fullOutput, translationsPath, translateMessages: true);
                    return 0;
                }
                finally
                {
                    try { Directory.Delete(downloadDirectory, recursive: true); }
                    catch (IOException) { }
                    catch (UnauthorizedAccessException) { }
                }
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
        Console.WriteLine("  native-title-patcher --download-diagnostics <full-preview.wad> <metadata-only.wad> [translation.json]");
        Console.WriteLine("  native-title-patcher --audit <input.wad> <report.json> [translation.json]");
        Console.WriteLine("  native-title-patcher --audit-latest <report.json> [translation.json]");
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

    private static void PatchTitle(string input, string output, string translationsPath, bool translateMessages = true)
    {
        input = Path.GetFullPath(input);
        output = Path.GetFullPath(output);
        translationsPath = Path.GetFullPath(translationsPath);
        if (!File.Exists(input)) throw new FileNotFoundException("Input WAD was not found.", input);
        if (translateMessages && !File.Exists(translationsPath))
            throw new FileNotFoundException("Translation resource was not found.", translationsPath);

        var translations = new Dictionary<string, string>(StringComparer.Ordinal);
        if (translateMessages)
        {
            using JsonDocument json = JsonDocument.Parse(File.ReadAllText(translationsPath));
            foreach (JsonProperty item in json.RootElement.EnumerateObject())
                translations[item.Name] = item.Value.GetString() ?? string.Empty;
        }

        using WAD wad = WAD.Load(input);
        ulong expectedTitleId = Convert.ToUInt64(OriginalTitleId, 16);
        if (wad.TitleID != expectedTitleId)
            throw new InvalidDataException(
                $"Input title ID is {wad.TitleID:X16}; expected Japanese TV no Tomo {OriginalTitleId}.");

        var patchedNames = new List<string>();
        var discoveredBmgFiles = new List<string>();
        int patchedMessages = 0;
        int patchedArchives = 0;

        if (translateMessages)
        {
            // The scanned native UI BMG files are in regular title content, not
            // the banner-app container. Keep content 0's U8 body untouched below.
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
        }

        // Both diagnostics retain the original title ID and region. libWiiSharp's
        // normal Save path reserializes the entire banner U8 and has produced a
        // content-0 SHA-1 mismatch in CI. Patch only the 0x640-byte IMET header in the
        // original byte array, then bypass banner-app serialization so every image,
        // layout and inner compressed stream remains byte-for-byte unchanged.
        PatchImetTitlesPreservingArchive(wad);
        DisableBannerArchiveReserialization(wad);
        wad.FakeSign = true;

        string? outputDirectory = Path.GetDirectoryName(output);
        if (!string.IsNullOrEmpty(outputDirectory)) Directory.CreateDirectory(outputDirectory);
        wad.Save(output);
        ValidateSavedWad(output, expectedTitleId);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            source = Path.GetFileName(input),
            output,
            mode = translateMessages ? "full-message-translation" : "title-metadata-only-control",
            originalTitleId = OriginalTitleId,
            outputTitleId = wad.TitleID.ToString("X16"),
            region = wad.Region.ToString(),
            preservedOriginalTitleId = wad.TitleID == expectedTitleId,
            translatedMessageCount = patchedMessages,
            patchedArchiveCount = patchedArchives,
            translatedResources = patchedNames,
            discoveredBmgResources = discoveredBmgFiles,
            localizedMenuTitleAllLanguages = true,
            preservedNativeExecutable = true,
            preservedOriginalBannerAnimationAndArtwork = true,
            warning = translateMessages
                ? "Full translation preview. If this shows black but the metadata-only control boots, one of the BMG/U8 replacements is responsible."
                : "Metadata-only control: original message archives and executable remain unmodified."
        }, new JsonSerializerOptions { WriteIndented = true }));
    }

    private static void ValidateSavedWad(string path, ulong expectedTitleId)
    {
        int[] repairedIndices;
        using (WAD saved = WAD.Load(path))
        {
            if (saved.TitleID != expectedTitleId)
                throw new InvalidDataException("Saved WAD title ID changed unexpectedly.");
            if (!saved.HasBanner)
                throw new InvalidDataException("Saved WAD banner container could not be parsed.");

            using var sha1 = System.Security.Cryptography.SHA1.Create();
            var repairable = new List<(TMD_Content Item, byte[] Hash)>();
            var badNonBanner = new List<int>();
            foreach (var item in saved.TmdContents)
            {
                byte[] content = saved.GetContentByIndex(item.Index);
                if ((ulong)content.Length != item.Size)
                    throw new InvalidDataException($"Saved WAD content {item.Index} size does not match the TMD.");
                byte[] hash = sha1.ComputeHash(content);
                if (hash.SequenceEqual(item.Hash)) continue;
                if (item.Index == 0) repairable.Add((item, hash));
                else badNonBanner.Add(item.Index);
            }

            if (badNonBanner.Count > 0)
                throw new InvalidDataException(
                    "Saved WAD content SHA-1 mismatch for non-banner indices: " +
                    string.Join(", ", badNonBanner));

            repairedIndices = repairable.Select(item => (int)item.Item.Index).ToArray();
            if (repairable.Count > 0)
            {
                foreach (var item in repairable)
                    item.Item.Hash = item.Hash;

                FieldInfo tmdField = typeof(WAD).GetField("tmd", BindingFlags.Instance | BindingFlags.NonPublic)
                    ?? throw new MissingFieldException("Could not access the in-memory TMD to repair its banner hash.");
                if (tmdField.GetValue(saved) is not TMD tmd)
                    throw new InvalidDataException("The saved WAD TMD object has an unexpected type.");

                tmd.FakeSign = true;
                byte[] tmdBytes = tmd.ToByteArray(true);
                byte[] wadBytes = File.ReadAllBytes(path);
                int expectedTmdSize = checked((int)ReadBeU32(wadBytes, 20));
                if (tmdBytes.Length != expectedTmdSize)
                    throw new InvalidDataException("Rebuilt TMD size does not match the WAD header.");
                int tmdOffset = FindTmdOffset(wadBytes);
                if (tmdOffset < 0 || tmdOffset + tmdBytes.Length > wadBytes.Length)
                    throw new InvalidDataException("TMD section lies outside the WAD.");

                Array.Copy(tmdBytes, 0, wadBytes, tmdOffset, tmdBytes.Length);
                File.WriteAllBytes(path, wadBytes);
                Console.WriteLine("Repaired banner TMD hash without changing banner content bytes.");
            }
        }

        using WAD verified = WAD.Load(path);
        if (verified.TitleID != expectedTitleId)
            throw new InvalidDataException("Repaired WAD title ID changed unexpectedly.");
        using var finalSha1 = System.Security.Cryptography.SHA1.Create();
        foreach (var item in verified.TmdContents)
        {
            byte[] content = verified.GetContentByIndex(item.Index);
            byte[] actual = finalSha1.ComputeHash(content);
            if ((ulong)content.Length != item.Size || !actual.SequenceEqual(item.Hash))
                throw new InvalidDataException(
                    $"Saved WAD content index {item.Index} still fails SHA-1 validation. " +
                    $"TMD={Convert.ToHexString(item.Hash)} actual={Convert.ToHexString(actual)} size={content.Length}.");
        }
        Console.WriteLine($"WAD reopen/content-hash validation passed: {Path.GetFileName(path)}; repaired indices={string.Join(",", repairedIndices)}");
    }

    private static int FindTmdOffset(byte[] wad)
    {
        const int alignment = 0x40;
        int cursor = Align(0x20, alignment);
        cursor = Align(checked(cursor + (int)ReadBeU32(wad, 8)), alignment);
        cursor = Align(checked(cursor + (int)ReadBeU32(wad, 12)), alignment);
        cursor = Align(checked(cursor + (int)ReadBeU32(wad, 16)), alignment);
        return cursor;
    }

    private static int Align(int value, int alignment) => checked((value + alignment - 1) & ~(alignment - 1));

    private static uint ReadBeU32(byte[] bytes, int offset)
    {
        if (offset < 0 || offset + 4 > bytes.Length)
            throw new InvalidDataException("WAD header field is outside the file.");
        return System.Buffers.Binary.BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset, 4));
    }

    private static void WriteNativeAudit(string input, string reportPath, string translationsPath)
    {
        input = Path.GetFullPath(input);
        reportPath = Path.GetFullPath(reportPath);
        translationsPath = Path.GetFullPath(translationsPath);
        if (!File.Exists(input)) throw new FileNotFoundException("Input WAD was not found.", input);
        if (!File.Exists(translationsPath)) throw new FileNotFoundException("Translation resource was not found.", translationsPath);

        var translations = new Dictionary<string, string>(StringComparer.Ordinal);
        using (JsonDocument json = JsonDocument.Parse(File.ReadAllText(translationsPath)))
            foreach (JsonProperty item in json.RootElement.EnumerateObject())
                translations[item.Name] = item.Value.GetString() ?? string.Empty;

        using WAD wad = WAD.Load(input);
        ulong expectedTitleId = Convert.ToUInt64(OriginalTitleId, 16);
        if (wad.TitleID != expectedTitleId)
            throw new InvalidDataException($"Input title ID is {wad.TitleID:X16}; expected Japanese TV no Tomo {OriginalTitleId}.");

        var snapshots = new List<BmgTranslator.FileSnapshot>();
        var resourceErrors = new List<object>();
        InventoryU8Archive(wad.BannerApp, "banner-app", snapshots, resourceErrors, 0);
        foreach (var entry in wad.TmdContents.Where(item => item.Index != 0).ToArray())
        {
            byte[] bytes;
            try { bytes = wad.GetContentByIndex(entry.Index); }
            catch { continue; }
            if (!CanLoadU8(bytes)) continue;
            try
            {
                using U8 archive = U8.Load(bytes);
                InventoryU8Archive(archive, $"{entry.Index:X4}", snapshots, resourceErrors, 0);
            }
            catch (Exception ex) when (ex is InvalidDataException or ArgumentException or IOException)
            {
                resourceErrors.Add(new { resource = $"{entry.Index:X4}", error = ex.Message });
            }
        }

        var matchedKeys = new HashSet<string>(StringComparer.Ordinal);
        var candidates = new List<object>();
        foreach (var file in snapshots)
        {
            foreach (var message in file.Messages)
            {
                string basename = Path.GetFileName(file.ResourceName);
                string? key = null;
                if (translations.ContainsKey($"{file.ResourceName}:{message.Index}"))
                    key = $"{file.ResourceName}:{message.Index}";
                else if (translations.ContainsKey($"{basename}:{message.Index}"))
                    key = $"{basename}:{message.Index}";
                if (key is null) continue;

                matchedKeys.Add(key);
                string proposed = translations[key];
                int[] placeholders = System.Text.RegularExpressions.Regex.Matches(proposed, @"#(\d{2})")
                    .Cast<System.Text.RegularExpressions.Match>()
                    .Select(match => int.Parse(match.Groups[1].Value))
                    .Distinct()
                    .OrderBy(index => index)
                    .ToArray();
                int[] sourcePlaceholders = System.Text.RegularExpressions.Regex.Matches(message.Text, @"#(\d{2})")
                    .Cast<System.Text.RegularExpressions.Match>()
                    .Select(match => int.Parse(match.Groups[1].Value))
                    .Distinct()
                    .OrderBy(index => index)
                    .ToArray();
                bool placeholderSafe = message.ControlTagCount == 0
                    ? placeholders.SequenceEqual(sourcePlaceholders)
                    : placeholders.SequenceEqual(Enumerable.Range(0, message.ControlTagCount));
                candidates.Add(new
                {
                    key,
                    file = file.ResourceName,
                    index = message.Index,
                    source = message.Text,
                    proposedEnglish = proposed,
                    sourceControlTagCount = message.ControlTagCount,
                    placeholderSafeForCurrentPatcher = placeholderSafe
                });
            }
        }

        var report = new
        {
            sourceTitleId = wad.TitleID.ToString("X16"),
            sourceFile = Path.GetFileName(input),
            fileCount = snapshots.Count,
            bmgFiles = snapshots.Select(file => new
            {
                file.ResourceName,
                file.EncodingId,
                file.EntrySize,
                messageCount = file.Messages.Count,
                controlTagMessages = file.Messages.Count(message => message.ControlTagCount > 0)
            }),
            allMessages = snapshots.SelectMany(file => file.Messages.Select(message => new
            {
                file = file.ResourceName,
                index = message.Index,
                source = message.Text,
                controlTagCount = message.ControlTagCount
            })),
            translationCandidates = candidates,
            unmatchedTranslationKeys = translations.Keys.Where(key => !matchedKeys.Contains(key)).OrderBy(key => key),
            resourceErrors
        };

        string? outputDirectory = Path.GetDirectoryName(reportPath);
        if (!string.IsNullOrEmpty(outputDirectory)) Directory.CreateDirectory(outputDirectory);
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"Native TV no Tomo audit: found {snapshots.Count} BMG resources and {candidates.Count} candidate translations.");
        Console.WriteLine($"Audit report written to: {reportPath}");
    }

    private static void InventoryU8Archive(
        U8 archive,
        string archivePath,
        List<BmgTranslator.FileSnapshot> snapshots,
        List<object> resourceErrors,
        int depth)
    {
        if (depth > 4) return;
        string[] names = archive.StringTable;
        U8_Node[] nodes = archive.Nodes.ToArray();
        byte[][] data = archive.Data;
        for (int i = 0; i < Math.Min(Math.Min(names.Length, nodes.Length), data.Length); i++)
        {
            if (nodes[i].Type != U8_NodeType.File || data[i].Length == 0) continue;
            string path = $"{archivePath}/{names[i]}";
            byte[] file = data[i];

            if (BmgTranslator.IsBmg(file))
            {
                try { snapshots.Add(BmgTranslator.Inspect(file, path)); }
                catch (Exception ex) { resourceErrors.Add(new { resource = path, error = ex.Message }); }
                continue;
            }

            if (!CanLoadU8(file)) continue;
            try
            {
                using U8 nested = U8.Load(file);
                InventoryU8Archive(nested, path, snapshots, resourceErrors, depth + 1);
            }
            catch (Exception ex) when (ex is InvalidDataException or ArgumentException or IOException)
            {
                resourceErrors.Add(new { resource = path, error = ex.Message });
            }
        }
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
