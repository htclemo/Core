<#
TheCore — mute / unmute every active Windows microphone (capture endpoint).

Uses inline C# (COM interop with the Core Audio API) so the Electron app does
not need a native module for this.  The Python app does the same thing through
pycaw.

Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File mic-mute.ps1 status
    powershell -NoProfile -ExecutionPolicy Bypass -File mic-mute.ps1 mute
    powershell -NoProfile -ExecutionPolicy Bypass -File mic-mute.ps1 unmute

Output: a single JSON object on stdout.
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "mute", "unmute")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$source = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace CoreAudio
{
    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    public class MMDeviceEnumerator { }

    public enum EDataFlow { Render, Capture, All }
    public enum ERole { Console, Multimedia, Communications }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
    public interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(EDataFlow dataFlow, uint stateMask,
            out IMMDeviceCollection devices);
        int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role,
            out IMMDevice device);
    }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E")]
    public interface IMMDeviceCollection
    {
        int GetCount(out uint count);
        int Item(uint index, out IMMDevice device);
    }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("D666063F-1587-4E43-81F1-B948E807363F")]
    public interface IMMDevice
    {
        int Activate(ref Guid iid, int clsCtx, IntPtr activationParams,
            [MarshalAs(UnmanagedType.IUnknown)] out object instance);
        int OpenPropertyStore(int stgmAccess, out IPropertyStore properties);
    }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    public interface IPropertyStore
    {
        int GetCount(out uint count);
        int GetAt(uint index, out PROPERTYKEY key);
        int GetValue(ref PROPERTYKEY key, out PropVariant value);
    }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
    public interface IAudioEndpointVolume
    {
        int RegisterControlChangeNotify(IntPtr notify);
        int UnregisterControlChangeNotify(IntPtr notify);
        int GetChannelCount(out uint count);
        int SetMasterVolumeLevel(float levelDb, ref Guid eventContext);
        int SetMasterVolumeLevelScalar(float level, ref Guid eventContext);
        int GetMasterVolumeLevel(out float levelDb);
        int GetMasterVolumeLevelScalar(out float level);
        int SetChannelVolumeLevel(uint channel, float levelDb, ref Guid eventContext);
        int SetChannelVolumeLevelScalar(uint channel, float level, ref Guid eventContext);
        int GetChannelVolumeLevel(uint channel, out float levelDb);
        int GetChannelVolumeLevelScalar(uint channel, out float level);
        int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, ref Guid eventContext);
        int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPERTYKEY
    {
        public Guid fmtid;
        public int pid;
    }

    // The native PROPVARIANT is 16 bytes: a 2-byte type, 6 bytes of padding
    // and an 8-byte union.  An explicit layout keeps the union at offset 8.
    [StructLayout(LayoutKind.Explicit)]
    public struct PropVariant
    {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(2)] public ushort wReserved1;
        [FieldOffset(4)] public ushort wReserved2;
        [FieldOffset(6)] public ushort wReserved3;
        [FieldOffset(8)] public IntPtr ptr;
        [FieldOffset(8)] public int cy;
    }

    public class MicInfo
    {
        public string Id = "";
        public string Name = "";
        public bool Muted = false;
    }

    public static class Mic
    {
        const uint DEVICE_STATE_ACTIVE = 0x1;
        const int CLSCTX_ALL = 23;
        const int STGM_READ = 0;

        static readonly Guid IID_AudioEndpointVolume =
            new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
        static readonly Guid PKEY_Device_FriendlyName =
            new Guid("A45C254A-DF1C-4EFD-8020-67D146A850E0");

        public static List<MicInfo> List()
        {
            var result = new List<MicInfo>();
            var enumerator = (IMMDeviceEnumerator)
                (new MMDeviceEnumerator());
            IMMDeviceCollection collection;
            Marshal.ThrowExceptionForHR(enumerator.EnumAudioEndpoints(
                EDataFlow.Capture, DEVICE_STATE_ACTIVE, out collection));

            uint count;
            Marshal.ThrowExceptionForHR(collection.GetCount(out count));

            for (uint i = 0; i < count; i++)
            {
                IMMDevice device;
                Marshal.ThrowExceptionForHR(collection.Item(i, out device));
                var info = new MicInfo();

                IPropertyStore store;
                int hr = device.OpenPropertyStore(STGM_READ, out store);
                if (hr != 0)
                {
                    System.Console.Error.WriteLine("OpenPropertyStore hr=" + hr);
                }
                if (hr == 0)
                {
                    // PKEY_Device_FriendlyName is pid 14; pid 2 is the
                    // device description and is used as a fallback.
                    int[] pids = new int[] { 14, 2 };
                    foreach (int pid in pids)
                    {
                        if (!String.IsNullOrEmpty(info.Name)) break;
                        var key = new PROPERTYKEY
                        {
                            fmtid = PKEY_Device_FriendlyName,
                            pid = pid
                        };
                        PropVariant value;
                        if (store.GetValue(ref key, out value) != 0) continue;
                        if (value.vt != 31) continue;
                        string name = Marshal.PtrToStringUni(value.ptr);
                        if (!String.IsNullOrEmpty(name)) info.Name = name;
                    }
                    Marshal.ReleaseComObject(store);
                }

                object raw;
                var iid = IID_AudioEndpointVolume;
                hr = device.Activate(ref iid, CLSCTX_ALL,
                    IntPtr.Zero, out raw);
                if (hr == 0)
                {
                    var volume = (IAudioEndpointVolume)raw;
                    bool muted;
                    if (volume.GetMute(out muted) == 0)
                    {
                        info.Muted = muted;
                    }
                    Marshal.ReleaseComObject(raw);
                }

                if (String.IsNullOrEmpty(info.Name))
                    info.Name = "Microphone " + (i + 1);
                result.Add(info);
            }
            return result;
        }

        public static int SetMuteAll(bool muted, out List<string> failed)
        {
            failed = new List<string>();
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumerator());
            IMMDeviceCollection collection;
            Marshal.ThrowExceptionForHR(enumerator.EnumAudioEndpoints(
                EDataFlow.Capture, DEVICE_STATE_ACTIVE, out collection));

            uint count;
            Marshal.ThrowExceptionForHR(collection.GetCount(out count));

            int changed = 0;
            for (uint i = 0; i < count; i++)
            {
                IMMDevice device;
                Marshal.ThrowExceptionForHR(collection.Item(i, out device));
                object raw;
                var iid = IID_AudioEndpointVolume;
                int hr = device.Activate(ref iid, CLSCTX_ALL,
                    IntPtr.Zero, out raw);
                if (hr != 0) continue;
                var volume = (IAudioEndpointVolume)raw;
                bool ok = false;
                try
                {
                    var ctx = Guid.Empty;
                    ok = volume.SetMute(muted, ref ctx) == 0;
                }
                catch { }
                if (ok) changed++;
                else failed.Add("device " + i);
                Marshal.ReleaseComObject(raw);
            }
            return changed;
        }
    }
}
'@

function New-Result {
    param($ok, $muted, $count, $message, $mics)
    $obj = [ordered]@{
        ok       = [bool]$ok
        muted    = [bool]$muted
        count    = [int]$count
        message  = [string]$message
        mics     = @($mics)
    }
    return ($obj | ConvertTo-Json -Compress -Depth 4)
}

try {
    Add-Type -TypeDefinition $source -Language CSharp
} catch {
    # Already loaded in this session — that is fine.  Anything else is fatal
    # and is reported on stderr.
    if ($_.Exception.Message -notmatch "already exists|already loaded") {
        [Console]::Error.WriteLine("Add-Type failed: " + $_.Exception.Message)
        Write-Output (New-Result -ok $false -muted $false -count 0 `
            -message "MIC CONTROL UNAVAILABLE" -mics @())
        exit 1
    }
}

try {
    $devices = [CoreAudio.Mic]::List()

    if ($Action -eq "status") {
        $allMuted = $true
        foreach ($d in $devices) { if (-not $d.Muted) { $allMuted = $false; break } }
        $names = @($devices | ForEach-Object { $_.Name })
        $state = if ($devices.Count -eq 0) { "NO MICS" } elseif ($allMuted) { "MUTED" } else { "LIVE" }
        Write-Output (New-Result -ok ($devices.Count -gt 0) -muted $allMuted -count $devices.Count `
            -message "ALL MICS $state ($($devices.Count))" -mics $names)
        exit 0
    }

    $wantMute = ($Action -eq "mute")
    $failed = New-Object System.Collections.Generic.List[string]
    $changed = [CoreAudio.Mic]::SetMuteAll($wantMute, [ref]$failed)

    $names = @($devices | ForEach-Object { $_.Name })
    $state = if ($wantMute) { "MUTED" } else { "LIVE" }
    if ($failed.Count -gt 0) {
        $msg = "MIC $state · $($failed.Count) ERROR(S)"
    } else {
        $msg = "ALL MICS $state ($($changed))"
    }
    Write-Output (New-Result -ok ($failed.Count -eq 0) -muted $wantMute -count $changed `
        -message $msg -mics $names)
    exit 0
} catch {
    Write-Output (New-Result -ok $false -muted $false -count 0 `
        -message "MIC CONTROL UNAVAILABLE: $($_.Exception.Message)" -mics @())
    exit 1
}
