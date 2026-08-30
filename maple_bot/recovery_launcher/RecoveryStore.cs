// 복구 파일 경로, JSON, SHA-256과 복구 폴더 권한을 관리한다.
using System;
using System.IO;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

internal sealed class RecoveryStore
{
    private static readonly Regex Sha256Pattern = new Regex(
        "^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant);
    private readonly JavaScriptSerializer _json = new JavaScriptSerializer();

    internal string RecoveryRoot { get; private set; }
    internal string InstallDirectory { get; private set; }
    internal string MetadataPath { get { return Path.Combine(RecoveryRoot, "recovery.json"); } }

    internal RecoveryStore(string recoveryRoot, string installDirectory)
    {
        RecoveryRoot = Path.GetFullPath(recoveryRoot);
        InstallDirectory = Path.GetFullPath(installDirectory);
    }

    internal static RecoveryStore CreateDefault(string installDirectory)
    {
        string programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        return new RecoveryStore(Path.Combine(programData, "Claude", "Recovery"), installDirectory);
    }

    internal void EnsureSecureDirectory()
    {
        Directory.CreateDirectory(RecoveryRoot);
        DirectorySecurity security = new DirectorySecurity();
        security.SetAccessRuleProtection(true, false);
        InheritanceFlags inherit = InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit;
        security.AddAccessRule(new FileSystemAccessRule(
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            FileSystemRights.FullControl, inherit, PropagationFlags.None, AccessControlType.Allow));
        security.AddAccessRule(new FileSystemAccessRule(
            new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null),
            FileSystemRights.FullControl, inherit, PropagationFlags.None, AccessControlType.Allow));
        security.AddAccessRule(new FileSystemAccessRule(
            new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null),
            FileSystemRights.ReadAndExecute, inherit, PropagationFlags.None, AccessControlType.Allow));
        Directory.SetAccessControl(RecoveryRoot, security);
    }

    internal RecoveryRunPaths ResetRunSignals()
    {
        RecoveryRunPaths paths = new RecoveryRunPaths
        {
            ReadyFile = Path.Combine(RecoveryRoot, "ready.json"),
            CrashFile = Path.Combine(RecoveryRoot, "last_crash.json"),
            NormalFile = Path.Combine(RecoveryRoot, "normal_exit.json")
        };
        DeleteIfPresent(paths.ReadyFile);
        DeleteIfPresent(paths.CrashFile);
        DeleteIfPresent(paths.NormalFile);
        return paths;
    }

    internal RecoveryValidation ValidatePreviousInstaller()
    {
        string metadataPath = MetadataPath;
        string installerPath = Path.Combine(RecoveryRoot, "previous_setup.exe");
        try
        {
            if (!File.Exists(metadataPath))
                return RecoveryValidation.Invalid("이전 버전 복구 정보가 없습니다.");
            if (!File.Exists(installerPath))
                return RecoveryValidation.Invalid("이전 버전 설치 파일이 없습니다.");
            RecoveryMetadata metadata = _json.Deserialize<RecoveryMetadata>(
                File.ReadAllText(metadataPath, Encoding.UTF8));
            if (metadata == null)
                return RecoveryValidation.Invalid("복구 정보 형식이 올바르지 않습니다.");
            if (!PathsEqual(metadata.installation_path, InstallDirectory))
                return RecoveryValidation.Invalid("복구 정보의 설치 경로가 현재 설치 경로와 다릅니다.");
            string expected = (metadata.previous_sha256 ?? string.Empty).Trim().ToLowerInvariant();
            if (!Sha256Pattern.IsMatch(expected))
                return RecoveryValidation.Invalid("복구 정보의 SHA-256이 올바르지 않습니다.");
            string actual = ComputeSha256(installerPath);
            if (!string.Equals(expected, actual, StringComparison.OrdinalIgnoreCase))
                return RecoveryValidation.Invalid("이전 버전 설치 파일의 SHA-256이 일치하지 않습니다.");
            return RecoveryValidation.Valid(installerPath, metadata);
        }
        catch (Exception error)
        {
            return RecoveryValidation.Invalid("복구 정보를 읽지 못했습니다: " + error.Message);
        }
    }

    internal ReleaseInfo ReadLocalRelease()
    {
        string path = Path.Combine(InstallDirectory, "release.json");
        try
        {
            ReleaseInfo release = _json.Deserialize<ReleaseInfo>(File.ReadAllText(path, Encoding.UTF8));
            UpdateClient.ValidateRelease(release);
            return release;
        }
        catch (Exception error)
        {
            throw new InvalidDataException("현재 버전 release.json을 읽지 못했습니다: " + error.Message, error);
        }
    }

    internal void CommitPreviousInstaller(string candidatePath, ReleaseInfo release)
    {
        UpdateClient.ValidateRelease(release);
        string candidate = Path.GetFullPath(candidatePath);
        if (!File.Exists(candidate)) throw new FileNotFoundException("복구 후보 설치 파일이 없습니다.", candidate);
        string actual = ComputeSha256(candidate);
        if (!string.Equals(actual, release.sha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("복구 후보 설치 파일의 SHA-256이 일치하지 않습니다.");

        string setupPath = Path.Combine(RecoveryRoot, "previous_setup.exe");
        string metadataTemp = Path.Combine(RecoveryRoot, "recovery.json.download");
        RecoveryMetadata metadata = new RecoveryMetadata
        {
            previous_version = release.version,
            current_version = release.version,
            installation_path = InstallDirectory,
            previous_sha256 = release.sha256.ToLowerInvariant(),
            created_at = DateTime.UtcNow.ToString("o")
        };
        File.WriteAllText(metadataTemp, _json.Serialize(metadata), new UTF8Encoding(false));
        ReplaceFile(candidate, setupPath);
        ReplaceFile(metadataTemp, MetadataPath);
    }

    internal CrashInfo ReadLastCrash()
    {
        return ReadCrash(Path.Combine(RecoveryRoot, "last_crash.json"));
    }

    internal CrashInfo ReadCrash(string path)
    {
        try
        {
            if (!File.Exists(path))
                return new CrashInfo { kind = "PROCESS_EXIT", message = "상세 오류 파일이 없습니다." };
            CrashInfo info = _json.Deserialize<CrashInfo>(File.ReadAllText(path, Encoding.UTF8));
            if (info == null) throw new InvalidDataException("empty JSON");
            return info;
        }
        catch (Exception error)
        {
            return new CrashInfo
            {
                kind = "CRASH_LOG_ERROR",
                message = "오류 기록을 읽지 못했습니다: " + error.Message,
                traceback = string.Empty
            };
        }
    }

    internal void WriteCrash(CrashInfo info)
    {
        File.WriteAllText(
            Path.Combine(RecoveryRoot, "last_crash.json"),
            _json.Serialize(info), new UTF8Encoding(false));
    }

    internal static string ComputeSha256(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 digest = SHA256.Create())
        {
            byte[] value = digest.ComputeHash(stream);
            StringBuilder text = new StringBuilder(value.Length * 2);
            foreach (byte item in value) text.Append(item.ToString("x2"));
            return text.ToString();
        }
    }

    internal static bool PathsEqual(string left, string right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right)) return false;
        string a = Path.GetFullPath(left).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string b = Path.GetFullPath(right).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return string.Equals(a, b, StringComparison.OrdinalIgnoreCase);
    }

    private static void DeleteIfPresent(string path)
    {
        try
        {
            if (File.Exists(path)) File.Delete(path);
        }
        catch
        {
        }
    }

    private static void ReplaceFile(string source, string destination)
    {
        if (File.Exists(destination))
        {
            string backup = destination + ".backup";
            if (File.Exists(backup)) File.Delete(backup);
            File.Replace(source, destination, backup, true);
            if (File.Exists(backup)) File.Delete(backup);
        }
        else
        {
            File.Move(source, destination);
        }
    }
}
