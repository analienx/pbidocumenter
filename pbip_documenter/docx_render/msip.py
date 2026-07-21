"""MSIP (Microsoft Information Protection) label injection."""

import os
import shutil
import tempfile
import typing
import zipfile
from datetime import datetime

MSIP_CUSTOM_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <property fmtid="{{<UUID_098>}}" pid="2" name="MSIP_Label_<LABEL_GUID>_Enabled"><vt:lpwstr>true</vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="3" name="MSIP_Label_<LABEL_GUID>_SetDate"><vt:lpwstr>{timestamp}</vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="4" name="MSIP_Label_<LABEL_GUID>_Method"><vt:lpwstr>Privileged</vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="5" name="MSIP_Label_<LABEL_GUID>_Name"><vt:lpwstr>English - Proprietary</vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="6" name="MSIP_Label_<LABEL_GUID>_SiteId"><vt:lpwstr><UUID_002></vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="7" name="MSIP_Label_<LABEL_GUID>_ContentBits"><vt:lpwstr>1</vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="8" name="ClassificationContentMarkingHeaderText"><vt:lpwstr>[Organization] Proprietary</vt:lpwstr></property>
  <property fmtid="{{<UUID_098>}}" pid="9" name="ClassificationContentMarkingHeaderFontProps"><vt:lpwstr>#00b294,12,Calibri</vt:lpwstr></property>
</Properties>"""


def inject_msip_label(docx_path: typing.Any) -> typing.Any:
    tmp = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(docx_path, "r") as z:
            z.extractall(tmp)
        dp = os.path.join(tmp, "docProps")
        os.makedirs(dp, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(os.path.join(dp, "custom.xml"), "w", encoding="utf-8") as f:
            f.write(MSIP_CUSTOM_XML.format(timestamp=ts))
        for path, tag, new in [
            (
                os.path.join(tmp, "[Content_Types].xml"),
                "</Types>",
                '  <Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>\n</Types>',
            ),
            (
                os.path.join(tmp, "_rels", ".rels"),
                "</Relationships>",
                '  <Relationship Id="rIdCustom" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties" Target="docProps/custom.xml"/>\n</Relationships>',
            ),
        ]:
            if os.path.exists(path):
                c = open(path, encoding="utf-8").read()
                if "custom.xml" not in c:
                    open(path, "w", encoding="utf-8").write(c.replace(tag, new))
        with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _dirs, files in os.walk(tmp):
                for fn in files:
                    fp = os.path.join(root, fn)
                    z.write(fp, os.path.relpath(fp, tmp))
        return True
    except Exception as e:
        print(f"  WARNING: MSIP injection failed: {e}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
