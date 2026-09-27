"""Which features a Shark robot has, by its model string, as the SharkClean app decides.

A port of the app's own capability logic (its embedded "launch" module, SharkClean
6.27.0). Almost everything follows from one string, the robot's cloud model
(``oem_model``, e.g. ``RV2500AWSX``): a table gives its family, the family its
classification, letters in the model prefix and a hex bitmask add hardware, and a
few exact model lists pick out product lines.

The model is not reported over local MQTT, so callers supply it. Features are
three-valued: ``True`` / ``False`` as the app would decide, or ``None`` when the
model is missing from the table (a retail SKU such as ``RV2610BFCA`` is not the
cloud model string) and a family-based answer cannot be given.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional

# Fs.robots: cloud model string -> family.
MODEL_FAMILIES: Dict[str, str] = {
    "AV752": "RandomBounceAV75",
    "AV753": "RandomBounceAV75",
    "AV911": "Mesa3",
    "AV911S": "Mesa3",
    "AV970": "Valley1",
    "AV990": "Valley2",
    "AV992": "Mesa3",
    "AV993": "Mesa3",
    "RV1000": "Valley1",
    "RV1000A": "Mesa1",
    "RV1000A-CN": "Mesa1",
    "RV1000ADev-CN": "RandomBounceOther",
    "RV1000A-EU": "Mesa1",
    "RV1000A-JP": "Mesa1",
    "RV1000A-UK": "Mesa1",
    "RV1000-CN": "Valley1",
    "RV1000Dev-CN": "RandomBounceOther",
    "RV1000-EU": "Valley1",
    "RV1000-JP": "Valley1",
    "RV1000-UK": "Valley1",
    "RV100V2": "Valley2",
    "RV100V3": "Valley2",
    "RV1100": "Valley2",
    "RV1100A": "Mesa2",
    "RV1100A2": "Mesa2",
    "RV1100A3": "Mesa2",
    "RV1100AA": "MesaAir",
    "RV1100AA-CN": "MesaAir",
    "RV1100AA-EU": "MesaAir",
    "RV1100AA-JP": "MesaAir",
    "RV1100AA-UK": "MesaAir",
    "RV1100AAX": "MesaAir",
    "RV1100AAXDev": "MesaAir",
    "RV1100AB": "Mesa2",
    "RV1100AC": "Mesa2",
    "RV1100A-CN": "Mesa2",
    "RV1100A-EU": "Mesa2",
    "RV1100A-JP": "Mesa2",
    "RV1100A-UK": "Mesa2",
    "RV1100AX": "Mesa2",
    "RV1100AXDev": "Mesa2",
    "RV1100-CN": "Valley2",
    "RV1100-EU": "Valley2",
    "RV1100-JP": "Valley2",
    "RV1100-UK": "Valley2",
    "RV1100V2": "Valley2",
    "RV1100V3": "Valley2",
    "RV1100VA": "ValleyAir",
    "RV1100VA-CN": "ValleyAir",
    "RV1100VA-EU": "ValleyAir",
    "RV1100VA-JP": "ValleyAir",
    "RV1100VA-UK": "ValleyAir",
    "RV1100VAX": "ValleyAir",
    "RV1100VAXDev": "ValleyAir",
    "RV1100VB": "ValleyAir",
    "RV1100VC": "ValleyAir",
    "RV1100X": "Valley2",
    "RV1100XDev": "Valley2",
    "RV1107": "Valley2",
    "RV1107A": "Mesa2",
    "RV1107VA": "ValleyAir",
    "RV1107AA": "MesaAir",
    "RV1107X": "Valley2",
    "RV1107AX": "Mesa2",
    "RV1107VAX": "ValleyAir",
    "RV1107AAX": "MesaAir",
    "RV19GyroDev": "RandomBounceOther",
    "RV19GyroPDev": "RandomBounceOther",
    "RV19OPPDev": "RandomBounceOther",
    "RV19PosDev": "RandomBounceOther",
    "RV2000D": "Gaia",
    "RV2000D-EU": "Gaia",
    "RV2000D-UK": "Gaia",
    "RV2000DX": "Gaia",
    "RV2000DXDev": "Gaia",
    "RV2000WD": "Poseidon",
    "RV2000WD-EU": "Poseidon",
    "RV2000WD-UK": "Poseidon",
    "RV2000WX": "Poseidon",
    "RV2000WXDev": "Poseidon",
    "RV2018Hill": "RandomBounceOther",
    "RV2018HillPlus": "RandomBounceOther",
    "RV2019QF": "Valley1",
    "RV2019QFA": "Mesa1",
    "RV2019QFA-CN": "RandomBounceOther",
    "RV2019QF-CN": "RandomBounceOther",
    "RV20GaiDev": "Gaia",
    "RV20PosDev": "Poseidon",
    "RV20QFADev": "Mesa3",
    "RV20QFDev": "Valley2",
    "RV2100DF": "Gaia",
    "RV2100DFDev": "Gaia",
    "RV2100WF": "Poseidon",
    "RV2100WFDev": "Poseidon",
    "RV21QFAADev": "MesaAir",
    "RV21QFADev": "Mesa3",
    "RV21QFDev": "Valley3",
    "RV21QFVADev": "ValleyAir",
    "RV2500A": "Three60",
    "RV2500A-EU": "Three60",
    "RV2500A-UK": "Three60",
    "RV2500AX": "Three60",
    "RV2500AXDev": "Three60",
    "RV360LDev": "Three60",
    "RV750": "RandomBounceRV75",
    "RV750G": "RandomBounceRV75",
    "RV750G-EU": "RandomBounceRV75",
    "RV750G-UK": "RandomBounceRV75",
    "RV750L": "RandomBounceRV75",
    "RV750L-CN": "RandomBounceRV75",
    "RV750LDev": "RandomBounceRV75",
    "RV750LDev-CN": "RandomBounceRV75",
    "RV750L-EU": "RandomBounceRV75",
    "RV750L-JP": "RandomBounceRV75",
    "RV750L-UK": "RandomBounceRV75",
    "RV750N": "RandomBounceRV75",
    "RV750NDev": "RandomBounceRV75",
    "RV750O": "RandomBounceRV75",
    "RV750P": "RandomBounceRV75",
    "RV750P-EU": "RandomBounceRV75",
    "RV750P-UK": "RandomBounceRV75",
    "RV750R": "RandomBounceRV75",
    "RV750RDev": "RandomBounceRV75",
    "RV750X": "RandomBounceRV75",
    "RV750XDev": "RandomBounceRV75",
    "RV754G-UK": "RandomBounceRV75",
    "RV754P-UK": "RandomBounceRV75",
    "RV850": "RandomBounceRV85",
    "RV850Dev": "RandomBounceRV85",
    "RV871": "RandomBounceRV87",
    "RV871-CN": "RandomBounceRV87",
    "RV871Dev": "RandomBounceRV87",
    "RV871Dev-CN": "RandomBounceRV87",
    "RV871-EU": "RandomBounceRV87",
    "RV871-JP": "RandomBounceRV87",
    "RV871P": "RandomBounceRV87",
    "RV871P-CN": "RandomBounceRV87",
    "RV871P-EU": "RandomBounceRV87",
    "RV871P-JP": "RandomBounceRV87",
    "RV871P-UK": "RandomBounceRV87",
    "RV871-UK": "RandomBounceRV87",
    "RV912": "MesaAir",
    "RV912S": "MesaAir",
    "RV912SCA": "MesaAir",
    "RV913S": "MesaAir",
    "RV914SCA": "MesaAir",
    "RV990CA": "ValleyAir",
    "RoboVac01": "RandomBounceOther",
    "RV360ZDev": "Three60",
    "RV2500AZ": "Three60",
    "RV1300S3EU": "MesaAir",
    "RV2500WD": "Three60WetDry",
    "RV2500WDDev": "Three60WetDry",
    "RV360LAFDev": "Three60",
    "RV360LWFDev": "Three60WetDry",
    "RV360LBFDev": "Three60WetDry",
    "RV2500AF": "Three60",
    "RV2500WF": "Three60WetDry",
    "RV2500BF": "Three60WetDry",
    "RV2500AF-EU": "Three60",
    "RV2500AF-UK": "Three60",
    "RV360LAWFXDev": "Three60WetDry",
    "RV360LAWFDev": "Three60WetDry",
    "RV360LAWXDev": "Three60WetDry",
    "RV360LAWDev": "Three60WetDry",
    "RV360LAFXDev": "Three60",
    "RV360LAXDev": "Three60",
    "RV360LADev": "Three60",
    "RV360LWFXDev": "Three60WetDry",
    "RV360LWXDev": "Three60WetDry",
    "RV360LWDev": "Three60WetDry",
    "RV360LFXDev": "Three60",
    "RV360LFDev": "Three60",
    "RV360LXDev": "Three60",
    "RV2300D": "Three60",
    "RV2300AE": "Three60",
    "RV2300S": "Three60",
    "RV2300D0-US": "Three60",
    "RV2300D0-JP": "Three60",
    "RV2300C0-US": "Three60",
    "RV2300E0-US": "Three60",
    "RV2300E0-EU": "Three60",
    "RV2300E0-JP": "Three60",
    "RV2500AWFX": "Three60WetDry",
    "RV2500AWF": "Three60WetDry",
    "RV2500AWX": "Three60WetDry",
    "RV2500AW": "Three60WetDry",
    "RV2500AFX": "Three60",
    "RV2500WFX": "Three60WetDry",
    "RV2500WX": "Three60WetDry",
    "RV2500W": "Three60WetDry",
    "RV2500FX": "Three60",
    "RV2500F": "Three60",
    "RV2500X": "Three60",
    "RV2500": "Three60",
    "RV2500AWFX-EU": "Three60WetDry",
    "RV2500AWF-EU": "Three60WetDry",
    "RV2500AWX-EU": "Three60WetDry",
    "RV2500AW-EU": "Three60WetDry",
    "RV2500AFX-EU": "Three60",
    "RV2500AX-EU": "Three60",
    "RV2500WFX-EU": "Three60WetDry",
    "RV2500WF-EU": "Three60WetDry",
    "RV2500WX-EU": "Three60WetDry",
    "RV2500W-EU": "Three60WetDry",
    "RV2500FX-EU": "Three60",
    "RV2500F-EU": "Three60",
    "RV2500X-EU": "Three60",
    "RV2500-EU": "Three60",
    "RV2500AWFX-UK": "Three60WetDry",
    "RV2500AWF-UK": "Three60WetDry",
    "RV2500AWX-UK": "Three60WetDry",
    "RV2500AW-UK": "Three60WetDry",
    "RV2500AFX-UK": "Three60",
    "RV2500AX-UK": "Three60",
    "RV2500WFX-UK": "Three60WetDry",
    "RV2500WF-UK": "Three60WetDry",
    "RV2500WX-UK": "Three60WetDry",
    "RV2500W-UK": "Three60WetDry",
    "RV2500FX-UK": "Three60",
    "RV2500F-UK": "Three60",
    "RV2500X-UK": "Three60",
    "RV2500-UK": "Three60",
    "RV360LVADev": "Three60",
    "RV360LVAXDev": "Three60",
    "RV360LAADev": "Three60",
    "RV360LAAXDev": "Three60",
    "RV2500VA": "Three60",
    "RV2500VAX": "Three60",
    "RV2500AA": "Three60",
    "RV2500AAX": "Three60",
    "RV2500VA-JP": "Three60",
    "RV365LAWFXDev": "Three60WetDry",
    "RV365LAWFDev": "Three60WetDry",
    "RV365LAWXDev": "Three60WetDry",
    "RV365LAWDev": "Three60WetDry",
    "RV365LAFXDev": "Three60",
    "RV365LAFDev": "Three60",
    "RV365LAXDev": "Three60",
    "RV365LADev": "Three60",
    "RV365LWFXDev": "Three60WetDry",
    "RV365LWFDev": "Three60WetDry",
    "RV365LWXDev": "Three60WetDry",
    "RV365LWDev": "Three60WetDry",
    "RV365LFXDev": "Three60",
    "RV365LFDev": "Three60",
    "RV365LXDev": "Three60",
    "RV365LDev": "Three60",
    "RV2500AA-EU": "Three60",
    "RV2500VA-EU": "Three60",
    "RV2500VA-UK": "Three60",
    "RV2500AA-UK": "Three60",
    "RV2500AA-JP": "Three60",
    "RV380LAWFDev": "Three60WetDry",
    "RV380LAWDev": "Three60WetDry",
    "RV380LWFDev": "Three60WetDry",
    "RV380LWDev": "Three60WetDry",
    "RV380LAWFXDev": "Three60WetDry",
    "RV380LAWXDev": "Three60WetDry",
    "RV380LWFXDev": "Three60WetDry",
    "RV380LWXDev": "Three60WetDry",
    "RV2500-JP": "Three60",
    "RV2500A-JP": "Three60",
    "RV2500AF-JP": "Three60",
    "RV2500AW-JP": "Three60WetDry",
    "RV2500AWF-JP": "Three60WetDry",
    "RV2500F-JP": "Three60",
    "RV2500W-JP": "Three60WetDry",
    "RV2500WF-JP": "Three60WetDry",
    "RV2505": "Three60",
    "RV2505-JP": "Three60",
    "RV2505A": "Three60",
    "RV2505A-JP": "Three60",
    "RV2505AF": "Three60",
    "RV2505AF-JP": "Three60",
    "RV2505AW": "Three60WetDry",
    "RV2505AW-JP": "Three60WetDry",
    "RV2505AWF": "Three60WetDry",
    "RV2505AWF-JP": "Three60WetDry",
    "RV2505F": "Three60",
    "RV2505F-JP": "Three60",
    "RV2505W": "Three60WetDry",
    "RV2505W-JP": "Three60WetDry",
    "RV2505WF": "Three60WetDry",
    "RV2505WF-JP": "Three60WetDry",
    "RV380LADev": "Three60",
    "RV380LAFDev": "Three60",
    "RV380LAFXDev": "Three60",
    "RV380LAXDev": "Three60",
    "RV380LDev": "Three60",
    "RV380LFDev": "Three60",
    "RV380LFXDev": "Three60",
    "RV380LXDev": "Three60",
    "RV360LAAPDev": "Three60",
    "RV360LVAPDev": "Three60",
    "RV360LAAXPDev": "Three60",
    "RV360LVAXPDev": "Three60",
    "RV2500AAP": "Three60",
    "RV2500AAXP": "Three60",
    "RV2500VAP": "Three60",
    "RV2500VAXP": "Three60",
    "RV2500AAP-JP": "Three60",
    "RV2500VAP-JP": "Three60",
    "RV2500AAP-EU": "Three60",
    "RV2500VAP-EU": "Three60",
    "RV2500AAP-UK": "Three60",
    "RV2500VAP-UK": "Three60",
    "RV2800AW": "Three60WetDry",
    "RV2800AWF": "Three60WetDry",
    "RV2800AWFX": "Three60WetDry",
    "RV2800AWX": "Three60WetDry",
    "RV2800W": "Three60WetDry",
    "RV2800WF": "Three60WetDry",
    "RV2800WFX": "Three60WetDry",
    "RV2800WX": "Three60WetDry",
    "RV2800A": "Three60",
    "RV2800AF": "Three60",
    "RV2800AFX": "Three60",
    "RV2800AX": "Three60",
    "RV2800": "Three60",
    "RV2800F": "Three60",
    "RV2800FX": "Three60",
    "RV2800X": "Three60",
    "RV2800AW-EU": "Three60WetDry",
    "RV2800AWFX-EU": "Three60WetDry",
    "RV2800AWX-EU": "Three60WetDry",
    "RV2800W-EU": "Three60WetDry",
    "RV2800WF-EU": "Three60WetDry",
    "RV2800WFX-EU": "Three60WetDry",
    "RV2800WX-EU": "Three60WetDry",
    "RV2800A-EU": "Three60",
    "RV2800AF-EU": "Three60",
    "RV2800AFX-EU": "Three60",
    "RV2800AX-EU": "Three60",
    "RV2800-EU": "Three60",
    "RV2800F-EU": "Three60",
    "RV2800FX-EU": "Three60",
    "RV2800X-EU": "Three60",
    "RV2800AW-UK": "Three60WetDry",
    "RV2800AWF-UK": "Three60WetDry",
    "RV2800AWFX-UK": "Three60WetDry",
    "RV2800AWX-UK": "Three60WetDry",
    "RV2800W-UK": "Three60WetDry",
    "RV2800WF-UK": "Three60WetDry",
    "RV2800WFX-UK": "Three60WetDry",
    "RV2800WX-UK": "Three60WetDry",
    "RV2800A-UK": "Three60",
    "RV2800AF-UK": "Three60",
    "RV2800AFX-UK": "Three60",
    "RV2800AX-UK": "Three60",
    "RV2800-UK": "Three60",
    "RV2800F-UK": "Three60",
    "RV2800FX-UK": "Three60",
    "RV2800X-UK": "Three60",
    "RV2500AABDev": "Three60",
    "RV2500AAXBDev": "Three60",
    "RV2500VABDev": "Three60",
    "RV2500VAXBDev": "Three60",
    "RV2500AAPBDev": "Three60",
    "RV2500AAXPBDev": "Three60",
    "RV2500VAPBDev": "Three60",
    "RV2500VAXPBDev": "Three60",
    "RV2500AABDev-JP": "Three60",
    "RV2500AAXBDev-JP": "Three60",
    "RV2500VABDev-JP": "Three60",
    "RV2500VAXBDev-JP": "Three60",
    "RV2500AAPBDev-JP": "Three60",
    "RV2500AAXPBDev-JP": "Three60",
    "RV2500VAPBDev-JP": "Three60",
    "RV2500VAXPBDev-JP": "Three60",
    "RV360LAABDev": "Three60",
    "RV360LAAXBDev": "Three60",
    "RV360LVABDev": "Three60",
    "RV360LVAXBDev": "Three60",
    "RV360LAAPBDev": "Three60",
    "RV360LAAXPBDev": "Three60",
    "RV360LVAPBDev": "Three60",
    "RV360LVAXPBDev": "Three60",
    "RV2500AAB-EU": "Three60",
    "RV2500AAXB-EU": "Three60",
    "RV2500VAB-EU": "Three60",
    "RV2500VAXB-EU": "Three60",
    "RV2500AAPB-EU": "Three60",
    "RV2500AAXPB-EU": "Three60",
    "RV2500VAPB-EU": "Three60",
    "RV2500VAXPB-EU": "Three60",
    "RV2500AAB-UK": "Three60",
    "RV2500AAXB-UK": "Three60",
    "RV2500VAB-UK": "Three60",
    "RV2500VAXB-UK": "Three60",
    "RV2500AAPB-UK": "Three60",
    "RV2500AAXPB-UK": "Three60",
    "RV2500VAPB-UK": "Three60",
    "RV2500VAXPB-UK": "Three60",
    "RV2500AAB": "Three60",
    "RV2500AAXB": "Three60",
    "RV2500VAB": "Three60",
    "RV2500VAXB": "Three60",
    "RV2500AAPB": "Three60",
    "RV2500AAXPB": "Three60",
    "RV2500VAPB": "Three60",
    "RV2500VAXPB": "Three60",
    "RV2500AAB-JP": "Three60",
    "RV2500AAXB-JP": "Three60",
    "RV2500VAB-JP": "Three60",
    "RV2500VAXB-JP": "Three60",
    "RV2500AAPB-JP": "Three60",
    "RV2500AAXPB-JP": "Three60",
    "RV2500VAPB-JP": "Three60",
    "RV2500VAXPB-JP": "Three60",
    "RV2500AWFB": "Three60WetDry",
    "RV2500AWFXB": "Three60WetDry",
    "RV2500AWB": "Three60WetDry",
    "RV2500AWXB": "Three60WetDry",
    "RV2500WFB": "Three60WetDry",
    "RV2500WFXB": "Three60WetDry",
    "RV2500WB": "Three60WetDry",
    "RV2500WXB": "Three60WetDry",
    "RV2500AWFB-JP": "Three60WetDry",
    "RV2500AWFXB-JP": "Three60WetDry",
    "RV2500AWB-JP": "Three60WetDry",
    "RV2500AWXB-JP": "Three60WetDry",
    "RV2500WFB-JP": "Three60WetDry",
    "RV2500WFXB-JP": "Three60WetDry",
    "RV2500WB-JP": "Three60WetDry",
    "RV2500WXB-JP": "Three60WetDry",
    "RV360LAWFBDev": "Three60WetDry",
    "RV360LAWFXBDev": "Three60WetDry",
    "RV360LAWBDev": "Three60WetDry",
    "RV360LAWXBDev": "Three60WetDry",
    "RV360LWFBDev": "Three60WetDry",
    "RV360LWFXBDev": "Three60WetDry",
    "RV360LWBDev": "Three60WetDry",
    "RV360LWXBDev": "Three60WetDry",
    "RV2500AWFB-EU": "Three60WetDry",
    "RV2500AWFXB-EU": "Three60WetDry",
    "RV2500AWB-EU": "Three60WetDry",
    "RV2500AWXB-EU": "Three60WetDry",
    "RV2500WFB-EU": "Three60WetDry",
    "RV2500WFXB-EU": "Three60WetDry",
    "RV2500WB-EU": "Three60WetDry",
    "RV2500WXB-EU": "Three60WetDry",
    "RV2500AWFB-UK": "Three60WetDry",
    "RV2500AWFXB-UK": "Three60WetDry",
    "RV2500AWB-UK": "Three60WetDry",
    "RV2500AWXB-UK": "Three60WetDry",
    "RV2500WFB-UK": "Three60WetDry",
    "RV2500WFXB-UK": "Three60WetDry",
    "RV2500WB-UK": "Three60WetDry",
    "RV2500WXB-UK": "Three60WetDry",
    "RV381LAWFDev": "Three60",
    "RV382LAWFDev": "Three60",
    "RV381LAWFUSDev": "Three60WetDry",
    "RV382LAWFUSDev": "Three60WetDry",
    "RV2530AWFB": "Three60WetDry",
    "RV2530WFB": "Three60WetDry",
    "RV2530AWB": "Three60WetDry",
    "RV2530WB": "Three60WetDry",
    "RV2530WFB-JP": "Three60WetDry",
    "RV2530AWB-JP": "Three60WetDry",
    "RV2530WB-JP": "Three60WetDry",
    "RV2530AWFB-EU": "Three60WetDry",
    "RV2530WFB-EU": "Three60WetDry",
    "RV2530AWB-EU": "Three60WetDry",
    "RV2530WB-EU": "Three60WetDry",
    "RV2530AWFB-UK": "Three60WetDry",
    "RV2530WFB-UK": "Three60WetDry",
    "RV2530AWB-UK": "Three60WetDry",
    "RV2530WB-UK": "Three60WetDry",
    "RV2810AWFB": "Three60WetDry",
    "RV2820AWFB": "Three60WetDry",
    "RV2810AWFB-JP": "Three60WetDry",
    "RV2820AWFB-JP": "Three60WetDry",
    "RV2810AWFB-EU": "Three60WetDry",
    "RV2820AWFB-EU": "Three60WetDry",
    "RV2810AWFB-UK": "Three60WetDry",
    "RV2820AWFB-UK": "Three60WetDry",
    "RV2810LEGAL": "Three60WetDry",
    "RV2820LEGAL": "Three60WetDry",
    "RV2830WFB": "Three60WetDry",
    "RV2830WFB-JP": "Three60WetDry",
    "RV2830WFB-EU": "Three60WetDry",
    "RV2830WFB-UK": "Three60WetDry",
    "RV2800AWF-EU": "Three60WetDry",
    "RV363LAWBDev": "Three60WetDry",
    "RV363LAWFBDev": "Three60WetDry",
    "RV363LWFBDev": "Three60WetDry",
    "RV363LWBDev": "Three60WetDry",
    "RV383LWFBDev": "Three60WetDry",
    "RV383LWFBUSDev": "Three60WetDry",
    "RV2530AWFB-JP": "Three60WetDry",
    "RV2530AWFB-MX": "Three60WetDry",
    "RV2530-0000007D": "Three60WetDry",
    "RV2530-0000007D-EU": "Three60WetDry",
    "RV2530-0000007D-UK": "Three60WetDry",
    "RV24SpLABDev": "Three60",
    "RV24SpLBDev": "Three60",
    "RV2100AB": "Three60",
    "RV2100AB-AZ": "Three60",
    "RV2100B": "Three60",
    "RV2100AB-MX": "Three60",
    "RV2100B-MX": "Three60",
    "RV2100AB-JP": "Three60",
    "RV2100B-JP": "Three60",
    "RV2100AB-UK": "Three60",
    "RV2100B-UK": "Three60",
    "RV2100AB-EU": "Three60",
    "RV2100B-EU": "Three60",
    "RV2800AWF-JP": "Three60WetDry",
    "RV2800AWFX-JP": "Three60WetDry",
    "RV2800AW-JP": "Three60WetDry",
    "RV2800AWX-JP": "Three60WetDry",
    "RV2800AF-JP": "Three60",
    "RV2800AFX-JP": "Three60",
    "RV2800A-JP": "Three60",
    "RV2800AX-JP": "Three60",
    "RV2800WF-JP": "Three60WetDry",
    "RV2800WFX-JP": "Three60WetDry",
    "RV2800W-JP": "Three60WetDry",
    "RV2800WX-JP": "Three60WetDry",
    "RV2800F-JP": "Three60",
    "RV2800FX-JP": "Three60",
    "RV2800-JP": "Three60",
    "RV2800X-JP": "Three60",
    "RV2500AWFB-MX": "Three60WetDry",
    "RV2500VAB-MX": "Three60",
    "RV2500AAB-MX": "Three60",
    "RV2500AAPB-MX": "Three60",
    "RV2710AWFB": "Three60WetDry",
    "RV2710AWFB-EU": "Three60WetDry",
    "RV2710AWFB-UK": "Three60WetDry",
    "RV2720AWFB": "Three60WetDry",
    "RV2720AWFB-EU": "Three60WetDry",
    "RV2720AWFB-UK": "Three60WetDry",
    "RV2720-0000B43F": "Three60WetDry",
    "RV2720-0000B43F-EU": "Three60WetDry",
    "RV2720-0000B43F-UK": "Three60WetDry",
    "RV2720-0000B43F-Dev": "Three60WetDry",
    "RV2720-0008343F": "Three60WetDry",
    "RV2720-0008343F-EU": "Three60WetDry",
    "RV2720-0008343F-UK": "Three60WetDry",
    "RV2720-0008343F-Dev": "Three60WetDry",
    "RV2720-000C143F": "Three60WetDry",
    "RV2720-000C143F-EU": "Three60WetDry",
    "RV2720-000C143F-UK": "Three60WetDry",
    "RV2720-000C143F-Dev": "Three60WetDry",
    "RV371LAWFDev": "Three60WetDry",
    "RV372LAWFDev": "Three60WetDry",
    "RV2900AWFSB": "Three60WetDry",
    "RV2900AWFB": "Three60WetDry",
    "RV2900AWFSB-EU": "Three60WetDry",
    "RV2900AWFSB-UK": "Three60WetDry",
    "RV2900AWFB-EU": "Three60WetDry",
    "RV2900AWFB-UK": "Three60WetDry",
    "RV390LAWFSDev": "Three60WetDry",
    "RV390LAWFDev": "Three60WetDry",
    "RV3000-001D5F7F": "Three60WetDry",
    "RV3000-001F5F7F": "Three60WetDry",
    "RV3000-001D5F7F-EU": "Three60WetDry",
    "RV3000-001F5F7F-EU": "Three60WetDry",
    "RV3000-001D5F7F-UK": "Three60WetDry",
    "RV3000-001D5F7F-CA": "Three60WetDry",
    "RV3000-001F5F7F-AZ": "Three60WetDry",
    "RV3000-001D5F7F-AZ": "Three60WetDry",
    "RV2800WA3ACAWAD": "Three60WetDry",
    "RV2800WA3ACAWHD": "Three60WetDry",
    "RV2800WA3ACHWHD": "Three60WetDry",
    "RV2900WA3ACAWAD": "Three60WetDry",
    "RV2900WA3ACAWHD": "Three60WetDry",
    "RV2900WA3ACHWHD": "Three60WetDry",
    "RV2900WA3HCAWAD": "Three60WetDry",
    "RV2900WA3HCAWHD": "Three60WetDry",
    "RV2900WA3HCHWHD": "Three60WetDry",
    "RV2900WA3ACAWAD-EU": "Three60WetDry",
    "RV2900WA3ACAWHD-EU": "Three60WetDry",
    "RV2900WA3ACHWHD-EU": "Three60WetDry",
    "RV2900WA3HCAWAD-EU": "Three60WetDry",
    "RV2900WA3HCAWHD-EU": "Three60WetDry",
    "RV2900WA3HCHWHD-EU": "Three60WetDry",
    "RV2900WA3ACAWAD-UK": "Three60WetDry",
    "RV2900WA3ACAWHD-UK": "Three60WetDry",
    "RV2900WA3ACHWHD-UK": "Three60WetDry",
    "RV2900WA3HCAWAD-UK": "Three60WetDry",
    "RV2900WA3HCAWHD-UK": "Three60WetDry",
    "RV2900WA3HCHWHD-UK": "Three60WetDry",
    "RV2900WA3ACAWAD-AZ": "Three60WetDry",
    "RV2900WA3ACAWHD-AZ": "Three60WetDry",
    "RV2900WA3ACHWHD-AZ": "Three60WetDry",
    "RV2900WA3HCAWAD-AZ": "Three60WetDry",
    "RV2900WA3HCAWHD-AZ": "Three60WetDry",
    "RV2900WA3HCHWHD-AZ": "Three60WetDry",
    "RV2500HOP": "Three60WetDry",
    "RV2500HOP-EU": "Three60WetDry",
    "RV2500HOPP2B": "Three60WetDry",
    "RV2500HOPP2B-EU": "Three60WetDry",
    "RV2500HOPP2NB": "Three60WetDry",
    "RV2500HOPP2NB-EU": "Three60WetDry",
    "RV2500HOPP4CB": "Three60WetDry",
    "RV2500HOPP4CB-UK": "Three60WetDry",
    "RV2500HOPP4CB-EU": "Three60WetDry",
    "RV2800FW3HWHD": "Three60WetDry",
    "RV2800FW3HWHD-EU": "Three60WetDry",
    "RV2800FW3HWHD-UK": "Three60WetDry",
    "RV2800FW3HWHD-CA": "Three60WetDry",
    "RV2800FW3AWAD": "Three60WetDry",
    "RV2800FW3AWAD-EU": "Three60WetDry",
    "RV2800FW3AWAD-UK": "Three60WetDry",
    "RV2800FW3AWAD-CA": "Three60WetDry",
    "RV2800FW3AWHD": "Three60WetDry",
    "RV2800FW3AWHD-EU": "Three60WetDry",
    "RV2800FW3AWHD-UK": "Three60WetDry",
}

_CLASSIFICATIONS: Dict[str, str] = {
    "Gaia": "LaserBot",
    "Poseidon": "LaserBot",
    "Mesa1": "MapBot",
    "Mesa2": "MapBot",
    "Mesa3": "MapBot",
    "MesaAir": "MapBot",
    "Valley1": "MapBot",
    "Valley2": "MapBot",
    "Valley3": "MapBot",
    "ValleyAir": "MapBot",
    "RandomBounceAV75": "RandomBounce",
    "RandomBounceRV75": "RandomBounce",
    "RandomBounceRV85": "RandomBounce",
    "RandomBounceRV87": "RandomBounce",
    "RandomBounceOther": "RandomBounce",
    "Three60": "Three60",
    "Three60WetDry": "Three60",
}

# Exact model lists (all Three60-class), as the app's switch statements have them.
RV3000_MODELS: FrozenSet[str] = frozenset(
    {
        "RV3000-001D5F7F",
        "RV3000-001F5F7F",
        "RV3000-001D5F7F-EU",
        "RV3000-001F5F7F-EU",
        "RV3000-001D5F7F-UK",
        "RV3000-001D5F7F-CA",
        "RV3000-001F5F7F-AZ",
        "RV3000-001D5F7F-AZ",
    }
)

OPP_MODELS: FrozenSet[str] = frozenset(
    {
        "RV2500HOP",
        "RV2500HOP-EU",
        "RV2500HOPP2B",
        "RV2500HOPP2B-EU",
        "RV2500HOPP2NB",
        "RV2500HOPP2NB-EU",
        "RV2500HOPP4CB",
        "RV2500HOPP4CB-UK",
        "RV2500HOPP4CB-EU",
        "RV2530-0000007D",
        "RV2530-0000007D-UK",
        "RV2530-0000007D-EU",
    }
)

SPOT_LIDAR_MODELS: FrozenSet[str] = frozenset(
    {
        "RV24SpLABDev",
        "RV24SpLBDev",
        "RV2100AB",
        "RV2100AB-AZ",
        "RV2100B",
    }
)

THREE60_EZ_MODELS: FrozenSet[str] = frozenset(
    {
        "RV360LVADev",
        "RV360LVAXDev",
        "RV360LAADev",
        "RV360LAAXDev",
        "RV2500VA",
        "RV2500VAX",
        "RV2500AA",
        "RV2500AAX",
        "RV2500VA-JP",
    }
)

ODM_MODELS: FrozenSet[str] = frozenset(
    {
        "RV2800WA3ACAWAD",
        "RV2800WA3ACAWHD",
        "RV2800WA3ACHWHD",
        "RV2900WA3ACAWAD",
        "RV2900WA3ACAWHD",
        "RV2900WA3ACHWHD",
        "RV2900WA3HCAWAD",
        "RV2900WA3HCAWHD",
        "RV2900WA3HCHWHD",
        "RV2900WA3ACAWAD-EU",
        "RV2900WA3ACAWHD-EU",
        "RV2900WA3ACHWHD-EU",
        "RV2900WA3HCAWAD-EU",
        "RV2900WA3HCAWHD-EU",
        "RV2900WA3HCHWHD-EU",
        "RV2900WA3ACAWAD-UK",
        "RV2900WA3ACAWHD-UK",
        "RV2900WA3ACHWHD-UK",
        "RV2900WA3HCAWAD-UK",
        "RV2900WA3HCAWHD-UK",
        "RV2900WA3HCHWHD-UK",
        "RV2900WA3ACAWAD-AZ",
        "RV2900WA3ACAWHD-AZ",
        "RV2900WA3ACHWHD-AZ",
        "RV2900WA3HCAWAD-AZ",
        "RV2900WA3HCAWHD-AZ",
        "RV2900WA3HCHWHD-AZ",
    }
)

MPP_MODELS: FrozenSet[str] = frozenset(
    {
        "RV2800FW3HWHD",
        "RV2800FW3HWHD-EU",
        "RV2800FW3HWHD-UK",
        "RV2800FW3HWHD-CA",
        "RV2800FW3AWAD",
        "RV2800FW3AWAD-EU",
        "RV2800FW3AWAD-UK",
        "RV2800FW3AWAD-CA",
        "RV2800FW3AWHD",
        "RV2800FW3AWHD-EU",
        "RV2800FW3AWHD-UK",
    }
)

# Bits of the hex feature mask in models like RV3000-001D5F7F, least significant first.
_MASK_BITS = ("WetDry", "FanJet", "AED", "Series 3", "Bluetooth", "Lidar", "Floor Detect")

_MAPPING_FAMILIES = frozenset(
    {"Gaia", "Poseidon", "Three60", "Three60WetDry", "Mesa1", "Mesa2", "Mesa3", "Valley1", "Valley2", "Valley3"}
)
_EXPLORE_FAMILIES = frozenset({"Gaia", "Poseidon", "Three60", "Three60WetDry"})
_DND_FAMILIES = _MAPPING_FAMILIES | {"MesaAir", "ValleyAir"}
_VALLEY_FAMILIES = frozenset({"Valley1", "Valley2", "Valley3", "ValleyAir"})
_MOPPING_FAMILIES = frozenset({"Poseidon", "Three60WetDry"})


@dataclass(frozen=True)
class RobotProfile:
    """The app's view of one robot model."""

    model: str

    @property
    def family(self) -> Optional[str]:
        """The model's family, or None when the app's table does not list it."""
        return MODEL_FAMILIES.get(self.model)

    @property
    def classification(self) -> Optional[str]:
        return _CLASSIFICATIONS.get(self.family) if self.family else None

    @property
    def known(self) -> bool:
        return self.family is not None

    # -- product lines (exact lists; an unlisted model is simply not one) ----

    def _in(self, models: FrozenSet[str]) -> bool:
        return self.classification == "Three60" and self.model in models

    @property
    def is_rv3000(self) -> bool:
        return self._in(RV3000_MODELS)

    @property
    def is_opp(self) -> bool:
        return self._in(OPP_MODELS)

    @property
    def is_spot_lidar(self) -> bool:
        return self._in(SPOT_LIDAR_MODELS)

    @property
    def is_360ez(self) -> bool:
        return self._in(THREE60_EZ_MODELS)

    # -- hardware from the model string -------------------------------------

    @property
    def _prefix(self) -> str:
        return self.model.split("-")[0]

    def _mask(self, bit: str) -> Optional[bool]:
        """A bit of the hex feature mask, or None when the model carries none."""
        parts = self.model.split("-")
        if len(parts) < 2 or len(parts[1]) < 8:
            return None
        try:
            value = int(parts[1], 16)
        except ValueError:
            return None
        return bool(value >> _MASK_BITS.index(bit) & 1)

    def _family_in(self, families: FrozenSet[str]) -> Optional[bool]:
        return None if self.family is None else self.family in families

    def _class_in(self, *classes: str) -> Optional[bool]:
        return None if self.classification is None else self.classification in classes

    # -- features, as the app gates them ------------------------------------

    @property
    def has_map(self) -> Optional[bool]:
        return self._family_in(_MAPPING_FAMILIES)

    @property
    def has_explore(self) -> Optional[bool]:
        return self._family_in(_EXPLORE_FAMILIES)

    @property
    def has_recharge_resume(self) -> Optional[bool]:
        return self._family_in(_MAPPING_FAMILIES)

    @property
    def has_auto_empty(self) -> Optional[bool]:
        """A self-emptying dock, so Evac & Resume."""
        if self._in(ODM_MODELS) or self._in(MPP_MODELS) or self.is_opp:
            return True
        masked = self._mask("AED")
        if masked is not None:
            return masked
        if "A" in self._prefix and "VA" not in self._prefix:
            return None if self.family is None else self.family not in _VALLEY_FAMILIES
        return False

    @property
    def has_fan_jet(self) -> bool:
        """CleanEdge air jets."""
        masked = self._mask("FanJet")
        return masked if masked is not None else "X" in self._prefix

    @property
    def do_not_disturb(self) -> Optional[bool]:
        return self._family_in(_DND_FAMILIES)

    @property
    def has_volume(self) -> Optional[bool]:
        """The app shows the volume slider to every robot but random-bounce ones."""
        return None if self.classification is None else self.classification != "RandomBounce"

    @property
    def has_pin_drop(self) -> Optional[bool]:
        """Spot clean by dropping a pin on the map."""
        if self.is_spot_lidar:
            return False
        return self._class_in("Three60", "LaserBot")

    @property
    def has_ultra_clean(self) -> Optional[bool]:
        """Matrix (two-pass) cleaning."""
        if self.is_spot_lidar or self.is_opp:
            return False
        return self._class_in("Three60", "LaserBot")

    @property
    def has_mopping(self) -> Optional[bool]:
        return self._family_in(_MOPPING_FAMILIES)

    # RV3000-only settings rows, and OPP-only carpet controls.

    @property
    def has_underglow_lights(self) -> bool:
        return self.is_rv3000

    @property
    def has_button_sounds(self) -> bool:
        return self.is_rv3000

    @property
    def has_carpet_boost(self) -> bool:
        return self.is_opp

    @property
    def has_carpet_detect(self) -> bool:
        return self.is_opp


# ---------------------------------------------------------------------------
# Robot types: the few groups every model falls into, for easy configuration
# ---------------------------------------------------------------------------

#: Robot types, in the order a picker should list them.
ROBOT_TYPES = ("lidar", "lidar_carpet", "rv3000", "spot_lidar", "map", "air", "basic")


@dataclass(frozen=True)
class Capabilities:
    """What a robot of one type offers, as plain yes/no answers.

    The two hardware extras that vary within a type - a self-emptying dock and
    CleanEdge air jets - are asked separately.
    """

    robot_type: str
    self_empty_dock: bool
    clean_edge: bool

    @property
    def _lidar(self) -> bool:
        return self.robot_type in ("lidar", "lidar_carpet", "rv3000", "spot_lidar")

    @property
    def has_map(self) -> bool:
        return self.robot_type not in ("air", "basic")

    @property
    def has_rooms(self) -> bool:
        return self.has_map

    @property
    def has_explore(self) -> bool:
        return self._lidar

    @property
    def has_pin_drop(self) -> bool:
        return self._lidar and self.robot_type != "spot_lidar"

    @property
    def has_ultra_clean(self) -> bool:
        return self._lidar and self.robot_type not in ("spot_lidar", "lidar_carpet")

    @property
    def has_recharge_resume(self) -> bool:
        return self.has_map

    @property
    def has_auto_empty(self) -> bool:
        return self.self_empty_dock

    @property
    def has_fan_jet(self) -> bool:
        return self.clean_edge

    @property
    def do_not_disturb(self) -> bool:
        return self.robot_type != "basic"

    @property
    def has_volume(self) -> bool:
        return self.robot_type != "basic"

    @property
    def has_underglow_lights(self) -> bool:
        return self.robot_type == "rv3000"

    @property
    def has_button_sounds(self) -> bool:
        return self.robot_type == "rv3000"

    @property
    def has_carpet_boost(self) -> bool:
        return self.robot_type == "lidar_carpet"

    @property
    def has_carpet_detect(self) -> bool:
        return self.robot_type == "lidar_carpet"


def robot_type(profile: RobotProfile) -> Optional[str]:
    """The robot type a known model belongs to, or None for a model the table lacks."""
    if profile.is_rv3000:
        return "rv3000"
    if profile.is_opp:
        return "lidar_carpet"
    if profile.is_spot_lidar:
        return "spot_lidar"
    if profile.family in ("MesaAir", "ValleyAir"):
        return "air"  # camera robots without a saved map
    return {
        "Three60": "lidar",
        "LaserBot": "lidar",
        "MapBot": "map",
        "RandomBounce": "basic",
    }.get(profile.classification or "")


def capabilities_for_model(model: str) -> Optional[Capabilities]:
    """Capabilities straight from a cloud model string, when the table knows it."""
    profile = RobotProfile(model)
    kind = robot_type(profile)
    if kind is None:
        return None
    return Capabilities(kind, bool(profile.has_auto_empty), profile.has_fan_jet)
