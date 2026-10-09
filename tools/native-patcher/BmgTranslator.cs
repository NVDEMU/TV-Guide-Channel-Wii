using libWiiSharp;
using System.Buffers.Binary;
using System.Text;
using System.Text.RegularExpressions;

namespace TvGuideNativePatcher;

internal static class BmgTranslator
{
    private sealed record Section(string Name, byte[] Bytes);
    private static readonly Encoding Utf16Be = Encoding.BigEndianUnicode;
    private static readonly Regex PlaceholderPattern = new(@"#(?<index>\d{2})", RegexOptions.Compiled | RegexOptions.CultureInvariant);

    public static bool IsBmg(byte[] original)
    {
        try
        {
            byte[] source = Headers.DetectHeader(original) == Headers.HeaderType.IMD5
                ? Headers.IMD5.RemoveHeader(original)
                : original;
            return source.Length >= 0x20 && source.AsSpan(0, 8).SequenceEqual("MESGbmg1"u8);
        }
        catch
        {
            return false;
        }
    }

    public sealed record MessageSnapshot(int Index, string Text, int ControlTagCount);
    public sealed record FileSnapshot(string ResourceName, byte EncodingId, int EntrySize, IReadOnlyList<MessageSnapshot> Messages);

    public static FileSnapshot Inspect(byte[] original, string resourceName)
    {
        byte[] source = Headers.DetectHeader(original) == Headers.HeaderType.IMD5
            ? Headers.IMD5.RemoveHeader(original)
            : original;
        if (source.Length < 0x20 || !source.AsSpan(0, 8).SequenceEqual("MESGbmg1"u8))
            throw new InvalidDataException($"{resourceName}: resource is not a BMG file.");

        int totalSize = checked((int)ReadU32(source, 8));
        if (totalSize < 0x20 || totalSize > source.Length)
            throw new InvalidDataException($"{resourceName}: BMG file size is invalid.");
        byte encodingId = source[0x10];
        Encoding encoding = ResolveEncoding(encodingId);
        bool isUtf16 = encodingId == 2;
        int sectionCount = checked((int)ReadU32(source, 12));
        int position = 0x20;
        byte[]? inf = null;
        byte[]? dat = null;
        for (int i = 0; i < sectionCount; i++)
        {
            if (position + 8 > totalSize) throw new InvalidDataException($"{resourceName}: section header is truncated.");
            string sectionName = Encoding.ASCII.GetString(source, position, 4);
            int size = checked((int)ReadU32(source, position + 4));
            if (size < 8 || position + size > totalSize) throw new InvalidDataException($"{resourceName}: invalid section size.");
            byte[] section = source.AsSpan(position, size).ToArray();
            if (sectionName == "INF1") inf = section;
            if (sectionName == "DAT1") dat = section;
            position += size;
        }
        if (inf is null || dat is null || inf.Length < 16 || dat.Length < 8)
            throw new InvalidDataException($"{resourceName}: missing or truncated INF1/DAT1 section.");

        int messageCount = ReadU16(inf, 8);
        int entrySize = ReadU16(inf, 10);
        if (entrySize < 4 || 16L + (long)messageCount * entrySize > inf.Length)
            throw new InvalidDataException($"{resourceName}: unsupported INF1 entry table.");
        var messages = new List<MessageSnapshot>(messageCount);
        for (int i = 0; i < messageCount; i++)
        {
            uint offset = ReadU32(inf, 16 + i * entrySize);
            int start = checked(8 + (int)offset);
            int end = FindTerminator(dat, start, isUtf16);
            byte[] raw = dat.AsSpan(start, end - start).ToArray();
            List<byte[]> tags = ExtractControlTags(raw, isUtf16);
            messages.Add(new MessageSnapshot(i, DecodeMessage(raw, encoding, isUtf16), tags.Count));
        }
        return new FileSnapshot(resourceName, encodingId, entrySize, messages);
    }

    private static string DecodeMessage(byte[] message, Encoding encoding, bool isUtf16)
    {
        int step = isUtf16 ? 2 : 1;
        int cursor = 0;
        int tagIndex = 0;
        var result = new StringBuilder();
        while (cursor < message.Length)
        {
            bool isTag = isUtf16
                ? cursor + 2 <= message.Length && ReadU16(message, cursor) == 0x001A
                : message[cursor] == 0x1A;
            if (!isTag)
            {
                int next = cursor + step;
                while (next < message.Length)
                {
                    bool nextIsTag = isUtf16
                        ? next + 2 <= message.Length && ReadU16(message, next) == 0x001A
                        : message[next] == 0x1A;
                    if (nextIsTag) break;
                    next += step;
                }
                result.Append(encoding.GetString(message, cursor, next - cursor));
                cursor = next;
                continue;
            }

            int lenOffset = cursor + step;
            int tagLength = message[lenOffset];
            result.Append($"#{tagIndex:00}");
            tagIndex++;
            cursor += tagLength;
        }
        return result.ToString();
    }

    public static byte[] Translate(byte[] original, string fileName, IReadOnlyDictionary<string, string> translations, out int count)
    {
        count = 0;
        bool hadImd5 = Headers.DetectHeader(original) == Headers.HeaderType.IMD5;
        byte[] source = hadImd5 ? Headers.IMD5.RemoveHeader(original) : original;
        if (source.Length < 0x20 || !source.AsSpan(0, 8).SequenceEqual("MESGbmg1"u8))
            return original;

        int totalSize = checked((int)ReadU32(source, 8));
        if (totalSize < 0x20 || totalSize > source.Length)
            throw new InvalidDataException($"{fileName}: BMG file size is invalid.");

        byte encodingId = source[0x10];
        Encoding textEncoding = ResolveEncoding(encodingId);
        bool isUtf16 = encodingId == 2;
        int charWidth = isUtf16 ? 2 : 1;
        int sectionCount = checked((int)ReadU32(source, 12));
        if (sectionCount < 2 || sectionCount > 64)
            throw new InvalidDataException($"{fileName}: invalid BMG section count {sectionCount}.");

        var sections = new List<Section>(sectionCount);
        int position = 0x20;
        for (int i = 0; i < sectionCount; i++)
        {
            if (position + 8 > totalSize)
                throw new InvalidDataException($"{fileName}: BMG section header {i} is truncated.");
            string sectionName = Encoding.ASCII.GetString(source, position, 4);
            int sectionLength = checked((int)ReadU32(source, position + 4));
            if (sectionLength < 8 || position + sectionLength > totalSize)
                throw new InvalidDataException($"{fileName}: section {sectionName} has an invalid size.");
            sections.Add(new Section(sectionName, source.AsSpan(position, sectionLength).ToArray()));
            position += sectionLength;
        }

        int infIndex = sections.FindIndex(s => s.Name == "INF1");
        int datIndex = sections.FindIndex(s => s.Name == "DAT1");
        if (infIndex < 0 || datIndex < 0)
            throw new InvalidDataException($"{fileName}: BMG requires INF1 and DAT1 sections.");

        byte[] inf = sections[infIndex].Bytes;
        byte[] dat = sections[datIndex].Bytes;
        if (inf.Length < 16 || dat.Length < 8)
            throw new InvalidDataException($"{fileName}: BMG INF1/DAT1 section is too short.");
        int messageCount = ReadU16(inf, 8);
        int entrySize = ReadU16(inf, 10);
        if (entrySize < 4 || 16L + (long)messageCount * entrySize > inf.Length)
            throw new InvalidDataException($"{fileName}: unsupported or truncated INF1 table.");

        using var payload = new MemoryStream();
        var newOffsets = new List<uint>(messageCount);
        var originalEntries = new List<byte[]>(messageCount);
        const int datPayloadStart = 8;

        for (int i = 0; i < messageCount; i++)
        {
            int entryOffset = 16 + i * entrySize;
            uint oldOffset = ReadU32(inf, entryOffset);
            long oldStartLong = (long)datPayloadStart + oldOffset;
            if (oldStartLong < datPayloadStart || oldStartLong + charWidth > dat.Length)
                throw new InvalidDataException($"{fileName}: message {i} offset is outside DAT1.");

            int oldStart = checked((int)oldStartLong);
            int oldEnd = FindTerminator(dat, oldStart, isUtf16);
            byte[] originalMessage = dat.AsSpan(oldStart, oldEnd - oldStart).ToArray();
            byte[] entry = inf.AsSpan(entryOffset, entrySize).ToArray();
            byte[] messageBytes = originalMessage;

            if (TryGetTranslation(translations, fileName, i, out string? translated)
                && TryEncodeTranslation(originalMessage, translated, textEncoding, isUtf16, out byte[] translatedBytes))
            {
                messageBytes = translatedBytes;
                count++;
            }

            newOffsets.Add(checked((uint)payload.Length));
            originalEntries.Add(entry);
            payload.Write(messageBytes);
            payload.Write(new byte[charWidth]);
        }

        if (count == 0)
            return original;

        byte[] newInf = BuildInfoSection(inf, entrySize, originalEntries, newOffsets);
        byte[] newDat = BuildDataSection(dat, payload.ToArray());
        sections[infIndex] = new Section("INF1", newInf);
        sections[datIndex] = new Section("DAT1", newDat);

        int outputSize = 0x20 + sections.Sum(s => s.Bytes.Length);
        byte[] output = new byte[outputSize];
        source.AsSpan(0, 0x20).CopyTo(output);
        WriteU32(output, 8, checked((uint)outputSize));
        WriteU32(output, 12, checked((uint)sections.Count));
        int writeAt = 0x20;
        foreach (Section section in sections)
        {
            section.Bytes.CopyTo(output, writeAt);
            writeAt += section.Bytes.Length;
        }

        // Preserve an existing IMD5 wrapper and recompute the hash after edits.
        return hadImd5 ? Headers.IMD5.AddHeader(output) : output;
    }

    private static Encoding ResolveEncoding(byte code)
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        return code switch
        {
            1 => Encoding.GetEncoding(1252, EncoderFallback.ExceptionFallback, DecoderFallback.ExceptionFallback),
            2 => Utf16Be,
            3 => Encoding.GetEncoding(932, EncoderFallback.ExceptionFallback, DecoderFallback.ExceptionFallback),
            4 => new UTF8Encoding(false, true),
            _ => throw new InvalidDataException($"Unsupported BMG character-set value {code}; expected 1, 2, 3 or 4.")
        };
    }

    private static bool TryGetTranslation(
        IReadOnlyDictionary<string, string> translations,
        string fileName,
        int messageIndex,
        out string? translated)
    {
        string normalized = fileName.Replace('\\', '/');
        string shortName = Path.GetFileName(normalized);
        return translations.TryGetValue($"{normalized}:{messageIndex}", out translated)
            || translations.TryGetValue($"{shortName}:{messageIndex}", out translated);
    }

    private static bool TryEncodeTranslation(
        byte[] originalMessage,
        string translated,
        Encoding encoding,
        bool isUtf16,
        out byte[] result)
    {
        MatchCollection matches = PlaceholderPattern.Matches(translated);
        List<byte[]> controlTags = ExtractControlTags(originalMessage, isUtf16);

        if (controlTags.Count == 0)
        {
            // A placeholder suggests a runtime field. Do not emit a visible "#00"
            // if its corresponding native control tag was not present in the source.
            if (matches.Count > 0)
            {
                result = originalMessage;
                return false;
            }
            result = encoding.GetBytes(translated.Replace("\\n", "\n", StringComparison.Ordinal));
            return true;
        }

        if (matches.Count == 0)
        {
            // Dropping binary tags can break dynamic data or text formatting. Skip
            // this entry unless the translation explicitly places every source tag.
            result = originalMessage;
            return false;
        }

        var usedIndices = matches.Cast<Match>().Select(m => int.Parse(m.Groups["index"].Value))
            .Distinct().OrderBy(i => i).ToArray();
        if (!usedIndices.SequenceEqual(Enumerable.Range(0, controlTags.Count)))
        {
            result = originalMessage;
            return false;
        }

        string normalizedText = translated.Replace("\\n", "\n", StringComparison.Ordinal);
        MatchCollection normalizedMatches = PlaceholderPattern.Matches(normalizedText);
        using var output = new MemoryStream();
        int cursor = 0;
        foreach (Match match in normalizedMatches)
        {
            output.Write(encoding.GetBytes(normalizedText[cursor..match.Index]));
            int tagIndex = int.Parse(match.Groups["index"].Value);
            output.Write(controlTags[tagIndex]);
            cursor = match.Index + match.Length;
        }
        output.Write(encoding.GetBytes(normalizedText[cursor..]));
        result = output.ToArray();
        return true;
    }

    private static List<byte[]> ExtractControlTags(byte[] message, bool isUtf16)
    {
        var tags = new List<byte[]>();
        int step = isUtf16 ? 2 : 1;
        for (int i = 0; i + step <= message.Length;)
        {
            bool isTag = isUtf16
                ? ReadU16(message, i) == 0x001A
                : message[i] == 0x1A;
            if (!isTag)
            {
                i += step;
                continue;
            }

            int lengthOffset = i + step;
            if (lengthOffset >= message.Length)
                throw new InvalidDataException("Truncated BMG control tag.");
            int tagLength = message[lengthOffset];
            if (tagLength < step + 4 || i + tagLength > message.Length || (isUtf16 && (tagLength & 1) != 0))
                throw new InvalidDataException("Invalid BMG control tag length.");
            tags.Add(message.AsSpan(i, tagLength).ToArray());
            i += tagLength;
        }
        return tags;
    }

    private static int FindTerminator(byte[] section, int start, bool isUtf16)
    {
        int step = isUtf16 ? 2 : 1;
        for (int i = start; i + step <= section.Length;)
        {
            if (isUtf16)
            {
                ushort unit = ReadU16(section, i);
                if (unit == 0) return i;
                if (unit == 0x001A)
                {
                    int lengthOffset = i + 2;
                    if (lengthOffset >= section.Length)
                        throw new InvalidDataException("Truncated BMG control tag.");
                    int tagLength = section[lengthOffset];
                    if (tagLength < 6 || i + tagLength > section.Length || (tagLength & 1) != 0)
                        throw new InvalidDataException("Invalid BMG control tag length.");
                    i += tagLength;
                    continue;
                }
            }
            else
            {
                if (section[i] == 0) return i;
                if (section[i] == 0x1A)
                {
                    int lengthOffset = i + 1;
                    if (lengthOffset >= section.Length)
                        throw new InvalidDataException("Truncated BMG control tag.");
                    int tagLength = section[lengthOffset];
                    if (tagLength < 5 || i + tagLength > section.Length)
                        throw new InvalidDataException("Invalid BMG control tag length.");
                    i += tagLength;
                    continue;
                }
            }
            i += step;
        }
        throw new InvalidDataException("BMG message has no terminator.");
    }

    private static byte[] BuildInfoSection(
        byte[] oldSection,
        int entrySize,
        IReadOnlyList<byte[]> oldEntries,
        IReadOnlyList<uint> offsets)
    {
        int length = Align(16 + offsets.Count * entrySize, 32);
        byte[] result = new byte[length];
        oldSection.AsSpan(0, Math.Min(16, oldSection.Length)).CopyTo(result);
        "INF1"u8.CopyTo(result);
        WriteU32(result, 4, checked((uint)length));
        WriteU16(result, 8, checked((ushort)offsets.Count));
        WriteU16(result, 10, checked((ushort)entrySize));
        for (int i = 0; i < offsets.Count; i++)
        {
            int entryOffset = 16 + i * entrySize;
            oldEntries[i].CopyTo(result, entryOffset);
            WriteU32(result, entryOffset, offsets[i]);
        }
        return result;
    }

    private static byte[] BuildDataSection(byte[] oldSection, byte[] payload)
    {
        int length = Align(8 + payload.Length, 32);
        byte[] result = new byte[length];
        oldSection.AsSpan(0, 8).CopyTo(result);
        "DAT1"u8.CopyTo(result);
        WriteU32(result, 4, checked((uint)length));
        payload.CopyTo(result, 8);
        return result;
    }

    public static void SelfTest()
    {
        // One UTF-16BE string "Old" at the start of DAT1's payload (offset 0).
        byte[] source = new byte[96];
        "MESGbmg1"u8.CopyTo(source);
        WriteU32(source, 8, (uint)source.Length);
        WriteU32(source, 12, 2);
        source[0x10] = 2;

        int inf = 32;
        "INF1"u8.CopyTo(source.AsSpan(inf, 4));
        WriteU32(source, inf + 4, 32);
        WriteU16(source, inf + 8, 1);
        WriteU16(source, inf + 10, 4);
        WriteU32(source, inf + 16, 0);

        int dat = 64;
        "DAT1"u8.CopyTo(source.AsSpan(dat, 4));
        WriteU32(source, dat + 4, 32);
        Utf16Be.GetBytes("Old").CopyTo(source, dat + 8);

        byte[] translated = Translate(source, "Test.bmg",
            new Dictionary<string, string> { ["Test.bmg:0"] = "New text" }, out int changed);
        if (changed != 1)
            throw new InvalidDataException($"Expected to translate one BMG message, found {changed}.");

        int translatedInf = 32;
        int translatedDat = translatedInf + checked((int)ReadU32(translated, translatedInf + 4));
        uint offset = ReadU32(translated, translatedInf + 16);
        int start = translatedDat + 8 + checked((int)offset);
        int end = FindTerminator(translated, start, true);
        string text = Utf16Be.GetString(translated, start, end - start);
        if (!string.Equals(text, "New text", StringComparison.Ordinal))
            throw new InvalidDataException($"BMG round-trip mismatch: '{text}'.");

        // A tag may contain null bytes. The terminator scanner must skip its payload.
        byte[] tagged = { 0x00, 0x1A, 0x06, 0x02, 0x00, 0x00, 0x00, 0x41, 0x00, 0x00 };
        int tagEnd = FindTerminator(tagged, 0, true);
        if (tagEnd != 8)
            throw new InvalidDataException($"BMG control-tag scan ended at {tagEnd} instead of 8.");
    }

    private static int Align(int value, int alignment) => (value + alignment - 1) & ~(alignment - 1);
    private static ushort ReadU16(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt16BigEndian(bytes.AsSpan(offset, 2));
    private static uint ReadU32(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset, 4));
    private static void WriteU16(byte[] bytes, int offset, ushort value) => BinaryPrimitives.WriteUInt16BigEndian(bytes.AsSpan(offset, 2), value);
    private static void WriteU32(byte[] bytes, int offset, uint value) => BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset, 4), value);
}
