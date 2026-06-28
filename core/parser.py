"""Parser for eMule / aMule ``*.part.met`` files.

This module contains the :class:`PartMetParser` class, which lets me read the
internal metadata of a ``.part.met`` file (the file eMule keeps in the
temporary folder alongside the ``.part`` file that holds the actual data).

From the ``.met`` file I extract, among other things, the three pieces of
information I need for MetGuardian:

1. the **file name** (``filename`` tag);
2. the **global MD4** of the file (``file_hash`` field, 16 bytes);
3. the list of **gaps** (the parts not yet downloaded).

The "number" of the file (e.g. ``493``) is NOT stored inside the ``.met``: it
is the file name on disk, so I derive it at a higher level, not here.

Notes on the format
-------------------
The ``.met`` is a little-endian binary format with this structure:

* 1 byte   -> version (I expect 0xE0, 0xE1 or 0xE2);
* for 0xE0 : 4 bytes date, then 16 bytes hash
* for 0xE1/0xE2: 16 bytes hash, then 4 bytes date
* 2 bytes  -> number of part hashes, followed by N 16-byte blocks;
* 4 bytes  -> number of tags, followed by the tags themselves.

Tags may have a compressed name (bit 0x80 set on the type) or an extended
name preceded by its length.

Module version
--------------
__version__ = "1.0.0"
"""

import struct
import binascii
from dataclasses import dataclass, field


# Internal version of this class. I bump it when I change its behavior, so I
# can track its evolution within the project.
__version__ = "1.1.0"


class PartMetParser:
    """Reads and interprets an eMule / aMule ``.part.met`` file.

    Typical usage::

        parser = PartMetParser()
        result = parser.parsePartMet("/path/493.part.met")
        if result is not None:
            print(result.tags.get("filename"))
            print(result.file_hash.hex())

    The main method is :meth:`parsePartMet`, which returns a :class:`PartMet`
    object if reading succeeds, or ``None`` if something goes wrong (file
    unreadable, truncated or corrupted). The fine distinction between "file
    inaccessible" and "file damaged" is handled at a higher level (in
    MetGuardian, inside ``core/reader.py``), not here.

    Attributes:
        partmet (PartMet): the last parsing result produced.
        file: the file object currently being read (set internally).
    """

    # Map of tag-name-ID -> human-readable name.
    # These are the "known" identifiers of the eMule format: when I encounter
    # one of these IDs in the file, I translate it into the matching name.
    TAG_NAMES = {
        0x01: "filename",
        0x02: "filesize",
        0x03: "filetype",
        0x04: "fileformat",
        0x05: "last_seen_complete",
        0x08: "transferred",
        0x09: "last_seen_complete",
        0x12: "partfilename",
        0x13: "gap_start",
        0x14: "gap_end",
        0x18: "dl_priority",
        0x19: "shared_upload",
        0x1A: "upload_priority",
        0x1B: "corrupted_parts",
        0x21: "dl_active_time",
        0x23: "status",
        0x27: "aich_hash",
        0x35: "part_hashes",
        0xD3: "media_length",
        0xD4: "media_bitrate",
        0xD5: "media_codec",
        0xFB: "filesize_hi",
    }

    # Map of tag-type-ID -> type name.
    # I keep it as a reference/documentation of the types the format defines.
    # NOTE to verify against the eMule spec: in the eDonkey protocol
    # 0x08 = UINT16 and 0x09 = UINT8. Here (and in the reading done in
    # read_tag) the two appear swapped. On my test files this causes no issue
    # because they don't contain these compact types, but if a ``.met`` ever
    # uses them this must be rechecked, otherwise the reading goes out of sync.
    TAG_TYPES = {
        0x01: "hash",
        0x02: "string",
        0x03: "uint32",
        0x04: "float32",
        0x05: "bool",
        0x07: "blob",
        0x08: "uint8",
        0x09: "uint16",
        0x0B: "uint64",
    }

    @dataclass
    class PartMet:
        """Container for the data extracted from a single ``.part.met`` file.

        Attributes:
            version (int): version byte of the file (expected 0xE0/0xE1/0xE2).
            file_hash (bytes): global MD4 of the file, 16 raw bytes.
                To get the hexadecimal form I use ``file_hash.hex()``.
            parts_hash (list[bytes]): list of the individual part hashes,
                each 16 bytes long.
            date (int): internal timestamp of the file (4 bytes).
            tags (dict): dictionary tag_name -> value (e.g. ``"filename"``).
            gaps (list): list of ``(start, end)`` tuples representing the byte
                ranges still to be downloaded.
        """

        version: int = 0
        file_hash: bytes = b''
        parts_hash: list[bytes] = field(default_factory=list[bytes])
        date: int = 0
        tags: dict = field(default_factory=dict)
        gaps: list = field(default_factory=list)

    def __init__(self):
        """Initialize the parser with an empty result and no open file."""
        # I prepare an empty container: it will be replaced on each parsePartMet.
        self.partmet = PartMetParser.PartMet()
        # No file associated yet.
        self.file = None

    def setFile(self, f):
        """Set the file to read from.

        Args:
            f: a file object opened in binary read mode (``'rb'``).
        """
        self.file = f

    def read_uint8(self):
        """Read an unsigned 8-bit integer (1 byte, little-endian).

        Returns:
            int: the value read.
        """
        return struct.unpack('<B', self.file.read(1))[0]

    def read_uint16(self):
        """Read an unsigned 16-bit integer (2 bytes, little-endian).

        Returns:
            int: the value read.
        """
        return struct.unpack('<H', self.file.read(2))[0]

    def read_uint32(self):
        """Read an unsigned 32-bit integer (4 bytes, little-endian).

        Returns:
            int: the value read.
        """
        return struct.unpack('<I', self.file.read(4))[0]

    def read_uint64(self):
        """Read an unsigned 64-bit integer (8 bytes, little-endian).

        Returns:
            int: the value read.
        """
        return struct.unpack('<Q', self.file.read(8))[0]

    def read_tag(self):
        """Read a single tag from the file and derive its name and value.

        A tag starts with a type byte. If the highest bit (0x80) is set, the
        tag name is "compressed" into a single byte (a known ID); otherwise
        the name is preceded by its length and can be a numeric ID (1 or 2
        bytes) or an actual string.

        Based on the type, I read the value with the correct size.

        Returns:
            tuple: a ``(name, value)`` pair where ``name`` is a string and
            ``value`` depends on the tag type (int, str, bytes, float, bool).

        Raises:
            ValueError: if I encounter a tag type I cannot interpret.
        """
        # Read the tag's type byte.
        tag_type = self.read_uint8()

        if tag_type & 0x80:
            # Compressed name: strip the 0x80 bit and read a single byte as ID.
            tag_type &= 0x7F
            name_id = self.read_uint8()
            name = self.TAG_NAMES.get(name_id, f"tag_0x{name_id:02x}")
        else:
            # Extended name: first the length, then the name bytes.
            name_len = self.read_uint16()
            raw_name = self.file.read(name_len)

            if name_len == 1:
                # Numeric ID on 1 byte.
                name_id = raw_name[0]
                name = self.TAG_NAMES.get(name_id, f"tag_0x{name_id:02x}")
            elif name_len == 2:
                ns, tag_id = raw_name[0], raw_name[1]
                # Gap tags use 2-byte names: first byte = FT_GAPSTART (0x09) or
                # FT_GAPEND (0x0A), second byte = gap index (starting at 0x30).
                if ns == 0x09:
                    name = "gap_start"
                elif ns == 0x0A:
                    name = "gap_end"
                else:
                    name = self.TAG_NAMES.get(tag_id, f"tag_0x{ns:02x}_{tag_id:02x}")
            else:
                # Actual textual name.
                name = raw_name.decode('utf-8', errors='replace')

        # Interpret the value based on the tag type.
        if tag_type == 0x02:
            # String: 2 bytes of length, then the characters.
            length = self.read_uint16()
            value = self.file.read(length).decode('utf-8', errors='replace')
        elif tag_type == 0x03:
            # 32-bit integer.
            value = self.read_uint32()
        elif tag_type == 0x0B:
            # 64-bit integer.
            value = self.read_uint64()
        elif tag_type == 0x01:
            # Hash: 16 raw bytes.
            value = self.file.read(16)
        elif tag_type == 0x07:
            # Blob: 4 bytes of length, then the raw bytes.
            length = self.read_uint32()
            value = self.file.read(length)
        elif tag_type == 0x08:
            # NOTE: see TAG_TYPES. Here I read 1 byte (to verify vs spec).
            value = self.read_uint8()
        elif tag_type == 0x09:
            # NOTE: see TAG_TYPES. Here I read 2 bytes (to verify vs spec).
            value = self.read_uint16()
        elif tag_type == 0x04:
            # 32-bit float.
            value = struct.unpack('<f', self.file.read(4))[0]
        elif tag_type == 0x05:
            # Boolean: 1 byte interpreted as true/false.
            value = bool(self.read_uint8())
        else:
            # Unhandled type: better to stop than to read garbage data.
            raise ValueError(f"Unknown tag type: 0x{tag_type:02x}")

        return name, value

    def parsePartMet(self, filepath) -> 'PartMetParser.PartMet':
        """Parse a ``.part.met`` file and return its data.

        This is the main method of the class. I open the file, check its
        version, read the global hash, the part hashes and all the tags,
        also rebuilding the list of gaps (missing parts).

        Args:
            filepath (str): path of the ``.part.met`` file to read.

        Returns:
            PartMet: the object with the extracted data if everything succeeds,
            otherwise ``None`` if the file is unreadable, truncated or corrupted.

        Note:
            Any error (file not openable, invalid structure, unsupported
            version) is caught and turned into a ``None``. In MetGuardian I
            then distinguish between "inaccessible" and "damaged" at a higher
            level, not inside this class.
        """
        try:
            # I always start from a clean container.
            self.partmet = PartMetParser.PartMet()
            with open(filepath, 'rb') as f:
                self.setFile(f)

                # I keep a hexadecimal copy of the whole file (useful for
                # debugging), then move the cursor back to the start for the
                # actual reading.
                self.HexData = binascii.hexlify(self.file.read())
                self.file.seek(0)

                # 1 byte: file version. I only accept the known versions.
                self.partmet.version = self.read_uint8()
                assert self.partmet.version in (0xE0, 0xE1, 0xE2), \
                    f"Unsupported version: {self.partmet.version:#x}"

                # The layout of date and hash depends on the version:
                #   0xE0 (old eMule / aMule): date(4) first, then hash(16)
                #   0xE1, 0xE2 (newer format): hash(16) first, then date(4)
                # Reading them in the wrong order embeds the mutable date bytes
                # in the hash, causing the hash to change on every eMule write
                # and triggering false REPLACED archiving each scan cycle.
                if self.partmet.version == 0xE0:
                    self.partmet.date = self.read_uint32()
                    self.partmet.file_hash = self.file.read(16)
                else:   # 0xE1 and 0xE2: hash comes first
                    self.partmet.file_hash = self.file.read(16)
                    self.partmet.date = self.read_uint32()

                # 2 bytes: number of part hashes; then N 16-byte blocks.
                numParts = self.read_uint16()
                if numParts > 0:
                    for i in range(0, numParts):
                        self.partmet.parts_hash.append(self.file.read(16))

                # 4 bytes: number of tags that follow.
                num_tags = self.read_uint32()

                tags = {}
                gap_starts = []
                gap_ends = []

                # I read the tags one by one. I collect gap_start / gap_end
                # separately to later pair them into (start, end) tuples.
                for _ in range(num_tags):
                    name, value = self.read_tag()
                    if value is None:
                        continue
                    if name == "gap_start":
                        gap_starts.append(value)
                    elif name == "gap_end":
                        gap_ends.append(value)
                    else:
                        tags[name] = value

                self.partmet.tags = tags
                # I pair the start and end of each gap.
                self.partmet.gaps = list(zip(gap_starts, gap_ends))
            return self.partmet
        except:
            # On any problem I return None: it will be the higher level that
            # decides whether the cause is an inaccessible or a corrupted file.
            return None
