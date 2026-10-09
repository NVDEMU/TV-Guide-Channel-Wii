using System.Buffers.Binary;
using System.Text;

namespace TvGuideNativePatcher;

internal static class BmgTranslator
{
    private sealed record Section(string Name, byte[] Bytes);
    private static readonly Encoding Utf16Be = Encoding.BigEndianUnicode;

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

        Encoding textEncoding = ResolveEncoding(source[0x10]);
        int charWidth = textEncoding == Utf16Be ? 2 : 1;
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
        int datPayloadStart = 8;
        for (int i = 0; i < messageCount; i++)
        {
            int entryOffset = 16 + i * entrySize;
            uint oldOffset = ReadU32(inf, entryOffset);
            long oldStartLong = (long)datPayloadStart + oldOffset;
            if (oldStartLong < datPayloadStart || oldStartLong + charWidth > dat.Length)
                throw new InvalidDataException($"{fileName}: message {i} offset is outside DAT1.");

            int oldStart = checked((int)oldStartLong);
            int oldEnd = FindTerminator(dat, oldStart, textEncoding);
            byte[] messageBytes = dat.AsSpan(oldStart, oldEnd - oldStart).ToArray();
            byte[] entry = inf.AsSpan(entryOffset, entrySize).ToArray();

            if (TryGetTranslation(translations, fileName, i, out string? translated))
            {
                messageBytes = textEncoding.GetBytes(translated.Replace("\\n", "\n", StringComparison.Ordinal));
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

        // Preserve an existing IMD5 wrapper and recompute its hash after the data changes.
        return hadImd5 ? Headers.IMD5.AddHeader(output) : output;
    }

    private static Encoding ResolveEncoding(byte code)
    {
        return code switch
        {
            0 => ResolveShiftJis(),
            1 => new UTF8Encoding(false, true),
            2 => Utf16Be,
            _ => throw new InvalidDataException($"Unsupported BMG text encoding value {code}.")
        };
    }

    private static Encoding ResolveShiftJis()
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        return Encoding.GetEncoding(932, EncoderFallback.ExceptionFallback, DecoderFallback.ExceptionFallback);
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

    private static int FindTerminator(byte[] section, int start, Encoding encoding)
    {
        int width = encoding == Utf16Be ? 2 : 1;
        for (int i = start; i + width <= section.Length; i += width)
        {
            if (width == 2)
            {
                if (section[i] == 0 && section[i + 1] == 0) return i;
            }
            else if (section[i] == 0)
            {
                return i;
            }
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
        // One string "Old" at the start of DAT1's payload (offset 0).
        byte[] source = new byte[96];
        "MESGbmg1"u8.CopyTo(source);
        WriteU32(source, 8, (uint)source.Length);
        WriteU32(source, 12, 2);
        source[0x10] = 2; // UTF-16BE

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
        int end = FindTerminator(translated, start, Utf16Be);
        string text = Utf16Be.GetString(translated, start, end - start);
        if (!string.Equals(text, "New text", StringComparison.Ordinal))
            throw new InvalidDataException($"BMG round-trip mismatch: '{text}'.");
    }

    private static int Align(int value, int alignment) => (value + alignment - 1) & ~(alignment - 1);
    private static ushort ReadU16(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt16BigEndian(bytes.AsSpan(offset, 2));
    private static uint ReadU32(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset, 4));
    private static void WriteU16(byte[] bytes, int offset, ushort value) => BinaryPrimitives.WriteUInt16BigEndian(bytes.AsSpan(offset, 2), value);
    private static void WriteU32(byte[] bytes, int offset, uint value) => BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset, 4), value);
}
