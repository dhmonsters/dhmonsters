// 임시 위치에서 현재 프로그램 파일만 정리하고 검증된 이전 설치기를 실행한다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class RollbackWorker
{
    private static readonly HashSet<string> CleanupNames = new HashSet<string>(
        new[] { "Claude.exe", "ClaudeApp.exe", "_internal", "core", "core_ui", "ui", "assets", "templates", "monsters", "models", "maps", "config.json", "version.txt", "release.json" },
        StringComparer.OrdinalIgnoreCase);

    internal static bool IsCleanupTarget(string name)
    {
        return CleanupNames.Contains(name ?? string.Empty);
    }

    internal static bool IsSafeInstallDirectory(string value)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(value)) return false;
            string path = Path.GetFullPath(value).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string root = Path.GetPathRoot(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (string.Equals(path, root, StringComparison.OrdinalIgnoreCase)) return false;
            return File.Exists(Path.Combine(path, "version.txt"));
        }
        catch
        {
            return false;
        }
    }

    internal static void StartDetached(RecoveryStore store)
    {
        RecoveryValidation validation = store.ValidatePreviousInstaller();
        if (!validation.IsValid) throw new InvalidOperationException(validation.Reason);
        string workerDirectory = Path.Combine(Path.GetTempPath(), "ClaudeRecovery");
        Directory.CreateDirectory(workerDirectory);
        string workerPath = Path.Combine(workerDirectory, "ClaudeRecoveryWorker.exe");
        File.Copy(Application.ExecutablePath, workerPath, true);
        ProcessStartInfo start = new ProcessStartInfo(workerPath);
        start.UseShellExecute = true;
        start.Arguments = "--rollback-worker " + Process.GetCurrentProcess().Id + " " + Quote(store.MetadataPath);
        Process.Start(start);
    }

    internal static int Run(string[] args)
    {
        try
        {
            if (args.Length != 3) throw new InvalidDataException("복구 작업자 인수가 올바르지 않습니다.");
            int parentPid;
            if (!int.TryParse(args[1], out parentPid)) throw new InvalidDataException("부모 프로세스 ID가 올바르지 않습니다.");
            string metadataPath = Path.GetFullPath(args[2]);
            string trustedRoot = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Claude", "Recovery");
            if (!RecoveryStore.PathsEqual(Path.GetDirectoryName(metadataPath), trustedRoot))
                throw new UnauthorizedAccessException("신뢰할 수 없는 복구 정보 경로입니다.");
            RecoveryMetadata metadata = new JavaScriptSerializer().Deserialize<RecoveryMetadata>(
                File.ReadAllText(metadataPath, Encoding.UTF8));
            if (metadata == null || !IsSafeInstallDirectory(metadata.installation_path))
                throw new UnauthorizedAccessException("안전하지 않은 설치 경로입니다.");
            RecoveryStore store = new RecoveryStore(trustedRoot, metadata.installation_path);
            RecoveryValidation validation = store.ValidatePreviousInstaller();
            if (!validation.IsValid) throw new InvalidDataException(validation.Reason);

            WaitForParent(parentPid);
            foreach (string name in CleanupNames)
            {
                string target = Path.Combine(store.InstallDirectory, name);
                if (Directory.Exists(target)) Directory.Delete(target, true);
                else if (File.Exists(target)) File.Delete(target);
            }

            ProcessStartInfo setup = new ProcessStartInfo(validation.InstallerPath);
            setup.UseShellExecute = true;
            setup.Arguments = "/SILENT /SUPPRESSMSGBOXES /NORESTART /DIR=" + Quote(store.InstallDirectory);
            using (Process installer = Process.Start(setup))
            {
                if (installer == null) throw new InvalidOperationException("이전 버전 설치기를 시작하지 못했습니다.");
                installer.WaitForExit();
                if (installer.ExitCode != 0) throw new InvalidOperationException("이전 버전 설치 실패 코드: " + installer.ExitCode);
            }
            Process.Start(new ProcessStartInfo(Path.Combine(store.InstallDirectory, "Claude.exe")) { UseShellExecute = true });
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show(error.ToString(), "Claude 이전 버전 복구 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    private static void WaitForParent(int pid)
    {
        try
        {
            using (Process parent = Process.GetProcessById(pid)) parent.WaitForExit(30000);
        }
        catch (ArgumentException)
        {
        }
    }

    private static string Quote(string value)
    {
        return "\"" + (value ?? string.Empty).Replace("\"", "\\\"") + "\"";
    }
}
