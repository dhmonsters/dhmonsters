// Qt와 Python에 의존하지 않고 실제 Claude 앱을 감시하는 복구 실행기 진입점이다.
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

internal static class Program
{
    private const string MutexName = "Global\\ClaudeRecoveryLauncher-7C8A5E21";

    [STAThread]
    internal static int Main(string[] args)
    {
        bool createdNew;
        using (Mutex instance = new Mutex(true, MutexName, out createdNew))
        {
            if (!createdNew)
            {
                MessageBox.Show("Claude가 이미 실행 중입니다.", "Claude", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return 0;
            }
            return RunManagedApplication(args);
        }
    }

    private static int RunManagedApplication(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        string installDirectory = Path.GetDirectoryName(Application.ExecutablePath);
        RecoveryStore store = RecoveryStore.CreateDefault(installDirectory);
        CrashInfo crash = null;
        int exitCode = 1;
        bool readySeen = false;
        bool normalSeen = false;
        try
        {
            store.EnsureSecureDirectory();
            RecoveryRunPaths paths = store.ResetRunSignals();
            string appPath = Path.Combine(installDirectory, "ClaudeApp.exe");
            ProcessStartInfo start = new ProcessStartInfo(appPath, JoinArguments(args));
            start.WorkingDirectory = installDirectory;
            start.UseShellExecute = false;
            start.EnvironmentVariables["CLAUDE_RECOVERY_MANAGED"] = "1";
            start.EnvironmentVariables["CLAUDE_RECOVERY_READY_FILE"] = paths.ReadyFile;
            start.EnvironmentVariables["CLAUDE_RECOVERY_CRASH_FILE"] = paths.CrashFile;
            start.EnvironmentVariables["CLAUDE_RECOVERY_NORMAL_FILE"] = paths.NormalFile;
            using (Process child = Process.Start(start))
            {
                if (child == null) throw new InvalidOperationException("ClaudeApp.exe를 시작하지 못했습니다.");
                child.WaitForExit();
                exitCode = child.ExitCode;
            }
            readySeen = File.Exists(paths.ReadyFile);
            normalSeen = File.Exists(paths.NormalFile);
            crash = store.ReadCrash(paths.CrashFile);
        }
        catch (Exception error)
        {
            crash = new CrashInfo
            {
                kind = "LAUNCH_ERROR",
                message = error.Message,
                traceback = error.ToString(),
                exit_code = 1,
                phase = FailurePhase.Startup
            };
            try { store.WriteCrash(crash); } catch { }
        }

        if (!LaunchDecision.ShouldShowRecovery(exitCode, readySeen, normalSeen)) return exitCode;
        crash = crash ?? new CrashInfo { kind = "PROCESS_EXIT", message = "ClaudeApp.exe가 비정상 종료되었습니다." };
        crash.exit_code = exitCode;
        crash.phase = LaunchDecision.GetFailurePhase(readySeen);
        MessageBox.Show(
            crash.message + Environment.NewLine + Environment.NewLine + "종료 코드: " + exitCode,
            "Claude 복구",
            MessageBoxButtons.OK,
            MessageBoxIcon.Error);
        return 0;
    }

    private static string JoinArguments(string[] args)
    {
        if (args == null || args.Length == 0) return string.Empty;
        string[] quoted = new string[args.Length];
        for (int index = 0; index < args.Length; index++)
            quoted[index] = "\"" + (args[index] ?? string.Empty).Replace("\"", "\\\"") + "\"";
        return string.Join(" ", quoted);
    }
}
