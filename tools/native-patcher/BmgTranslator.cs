using System.Buffers.Binary;
using System.Text;
using System.Text.Json;

namespace TvGuideNativePatcher;

internal static class BmgTranslator
{
    private static readonly Encoding BigEndianUtf16 = Encoding.BigEndianUnicode;

    public static byte[] Translate(byte[] source, string fileName, IReadOnlyDictionary<string, string> translations, out int count)
    {
        count = 0;
        if (source.Length < 0x40 || !source.AsSpan(0, 8).SequenceEqual("MESGbmg1"u8))
            return source;

        int totalSize = checked((int)ReadU32(source, 8));
        if (totalSize > source.Length || totalSize < 0x30)
            throw new InvalidDataException($"{fileName}: BMG file size is invalid.");

        int infOffset = FindSection(source, "INF1");
        int infSize = checked((int)ReadU32(source, infOffset + 4));
        int messageCount = ReadU16(source, infOffset + 8);
        int entrySize = ReadU16(source, infOffset + 10);
        if (entrySize != 4 || infSize < 16 + messageCount * entrySize)
            throw new InvalidDataException($"{fileName}: unsupported BMG INF1 table.");

        int datOffset = FindSection(source, "DAT1");
        int datSize = checked((int)ReadU32(source, datOffset + 4));
        int datPayload = datOffset + 8;
        if (datSize < 8 || datOffset + datSize > totalSize)
            throw new InvalidDataException($"{fileName}: invalid BMG DAT1 section.");

        var payload = new MemoryStream();
        payload.WriteByte(0);
        payload.WriteByte(0); // The original format starts message offsets after a 2-byte sentinel.
        var messageOffsets = new List<uint>(messageCount);

        for (int i = 0; i < messageCount; i++)
        {
            uint oldOffset = ReadU32(source, infOffset + 16 + i * entrySize);
            long oldStartLong = (long)datPayload + oldOffset;
            if (oldStartLong < datPayload || oldStartLong + 2 > (long)datOffset + datSize)
                throw new InvalidDataException($"{fileName}: message {i} offset is outside DAT1.");
            int oldStart = (int)oldStartLong;
            int oldEnd = FindNullTerminator(source, oldStart, datOffset + datSize);
            byte[] messageBytes = source.AsSpan(oldStart, oldEnd - oldStart).ToArray();

            if (translations.TryGetValue($"{fileName}:{i}", out string? translated))
            {
                messageBytes = BigEndianUtf16.GetBytes(translated.Replace("\\n", "\n", StringComparison.Ordinal));
                count++;
            }

            messageOffsets.Add((uint)payload.Length);
            payload.Write(messageBytes);
            payload.WriteByte(0);
            payload.WriteByte(0);
        }

        byte[] infSection = BuildInfoSection(source.AsSpan(infOffset, 16).ToArray(), messageCount, messageOffsets);
        byte[] datPayloadBytes = payload.ToArray();
        int datSectionLength = Align(8 + datPayloadBytes.Length, 32);
        byte[] datSection = new byte[datSectionLength];
        "DAT1"u8.CopyTo(datSection);
        WriteU32(datSection, 4, (uint)datSectionLength);
        datPayloadBytes.CopyTo(datSection, 8);

        int newTotal = 32 + infSection.Length + datSection.Length;
        byte[] result = new byte[newTotal];
        source.AsSpan(0, 32).CopyTo(result);
        WriteU32(result, 8, (uint)newTotal);
        WriteU32(result, 12, 2);
        int writeAt = 32;
        infSection.CopyTo(result, writeAt);
        writeAt += infSection.Length;
        datSection.CopyTo(result, writeAt);
        return result;
    }

    private static byte[] BuildInfoSection(byte[] oldHeader, int count, IReadOnlyList<uint> offsets)
    {
        int length = Align(16 + count * 4, 32);
        byte[] result = new byte[length];
        oldHeader.CopyTo(result, 0);
        WriteU32(result, 4, (uint)length);
        WriteU16(result, 8, (ushort)count);
        WriteU16(result, 10, 4);
        for (int i = 0; i < count; i++) WriteU32(result, 16 + i * 4, offsets[i]);
        return result;
    }

    private static int FindSection(byte[] source, string name)
    {
        int limit = checked((int)Math.Min(ReadU32(source, 8), (uint)source.Length));
        for (int i = 0x20; i + 8 <= limit; i += 4)
        {
            if (source.AsSpan(i, 4).SequenceEqual(Encoding.ASCII.GetBytes(name))) return i;
        }
        throw new InvalidDataException($"BMG has no {name} section.");
    }

    private static int FindNullTerminator(byte[] source, int start, int limit)
    {
        for (int i = start; i + 1 < limit; i += 2)
            if (source[i] == 0 && source[i + 1] == 0) return i;
        throw new InvalidDataException("BMG message has no terminator.");
    }

    private static int Align(int value, int alignment) => (value + alignment - 1) & ~(alignment - 1);
    private static ushort ReadU16(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt16BigEndian(bytes.AsSpan(offset, 2));
    private static uint ReadU32(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset, 4));
    private static void WriteU16(byte[] bytes, int offset, ushort value) => BinaryPrimitives.WriteUInt16BigEndian(bytes.AsSpan(offset, 2), value);
    private static void WriteU32(byte[] bytes, int offset, uint value) => BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset, 4), value);
}
