// 복구 실행기의 종료 판정과 저장소 무결성을 실제 C# 코드로 검증한다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class RecoveryLauncherTests
{
    private static int _failures;

    private static void AssertTrue(bool value, string name)
    {
        if (!value)
        {
            Console.Error.WriteLine("FAIL " + name);
            _failures++;
        }
    }

    private static void AssertFalse(bool value, string name)
    {
        AssertTrue(!value, name);
    }

    private static void AssertEqual(object expected, object actual, string name)
    {
        if (!object.Equals(expected, actual))
        {
            Console.Error.WriteLine("FAIL " + name + " expected=" + expected + " actual=" + actual);
            _failures++;
        }
    }

    private static string Sha256(byte[] content)
    {
        using (SHA256 digest = SHA256.Create())
        {
            byte[] value = digest.ComputeHash(content);
            StringBuilder text = new StringBuilder(value.Length * 2);
            foreach (byte item in value) text.Append(item.ToString("x2"));
            return text.ToString();
        }
    }

    private static void TestLaunchDecision()
    {
        AssertFalse(LaunchDecision.ShouldShowRecovery(0, true, false), "normal zero exit");
        AssertFalse(LaunchDecision.ShouldShowRecovery(23, true, true), "explicit normal marker");
        AssertTrue(LaunchDecision.ShouldShowRecovery(1, false, false), "startup failure");
        AssertTrue(LaunchDecision.ShouldShowRecovery(unchecked((int)0xC0000005), true, false), "native crash");
        AssertEqual(FailurePhase.Startup, LaunchDecision.GetFailurePhase(false), "startup phase");
        AssertEqual(FailurePhase.Runtime, LaunchDecision.GetFailurePhase(true), "runtime phase");
    }

    private static void TestRecoveryStoreValidation(string root)
    {
        string recovery = Path.Combine(root, "Recovery");
        string install = Path.Combine(root, "Install");
        Directory.CreateDirectory(recovery);
        Directory.CreateDirectory(install);
        byte[] setup = Encoding.UTF8.GetBytes("known previous installer");
        string setupPath = Path.Combine(recovery, "previous_setup.exe");
        File.WriteAllBytes(setupPath, setup);
        RecoveryMetadata metadata = new RecoveryMetadata();
        metadata.previous_version = "2.4.6";
        metadata.current_version = "2.4.7";
        metadata.installation_path = install;
        metadata.previous_sha256 = Sha256(setup);
        metadata.created_at = "2026-08-30T00:00:00Z";
        File.WriteAllText(
            Path.Combine(recovery, "recovery.json"),
            new JavaScriptSerializer().Serialize(metadata),
            new UTF8Encoding(false));

        RecoveryStore store = new RecoveryStore(recovery, install);
        RecoveryValidation valid = store.ValidatePreviousInstaller();
        AssertTrue(valid.IsValid, "valid cached installer");
        AssertEqual("2.4.6", valid.Metadata.previous_version, "previous version");

        File.WriteAllBytes(setupPath, Encoding.UTF8.GetBytes("tampered"));
        RecoveryValidation invalid = store.ValidatePreviousInstaller();
        AssertFalse(invalid.IsValid, "tampered installer rejected");
        AssertTrue(invalid.Reason.Contains("SHA-256"), "tampered reason");
    }

    private static void TestMalformedCrashIsSafe(string root)
    {
        string recovery = Path.Combine(root, "Malformed");
        Directory.CreateDirectory(recovery);
        File.WriteAllText(Path.Combine(recovery, "last_crash.json"), "not-json");
        RecoveryStore store = new RecoveryStore(recovery, Path.Combine(root, "Install2"));
        CrashInfo crash = store.ReadLastCrash();
        AssertTrue(crash.message.Contains("읽지 못했습니다"), "malformed crash fallback");
    }

    private static void TestUpdatePolicyAndUrl()
    {
        AssertTrue(UpdateClient.IsAllowedReleaseUrl(
            "https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.7/Claude_v2.4.7_Setup.exe"),
            "official release URL");
        AssertFalse(UpdateClient.IsAllowedReleaseUrl("http://github.com/dhmonsters/dhmonsters/releases/download/v2/a.exe"), "HTTP rejected");
        AssertFalse(UpdateClient.IsAllowedReleaseUrl("https://example.com/Claude.exe"), "foreign host rejected");
        AssertEqual(UpdateAction.Update, UpdatePolicy.Decide("2.4.7", "2.4.8"), "newer update");
        AssertEqual(UpdateAction.Reinstall, UpdatePolicy.Decide("2.4.7", "2.4.7"), "same reinstall");
        AssertEqual(UpdateAction.None, UpdatePolicy.Decide("2.4.7", "2.4.6"), "older ignored");
    }

    private static void TestCommitPreviousInstaller(string root)
    {
        string recovery = Path.Combine(root, "CommitRecovery");
        string install = Path.Combine(root, "CommitInstall");
        Directory.CreateDirectory(recovery);
        Directory.CreateDirectory(install);
        string candidate = Path.Combine(root, "candidate.exe");
        byte[] content = Encoding.UTF8.GetBytes("current official setup");
        File.WriteAllBytes(candidate, content);
        ReleaseInfo release = new ReleaseInfo
        {
            version = "2.4.7",
            download_url = "https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.7/Claude_v2.4.7_Setup.exe",
            sha256 = Sha256(content)
        };

        RecoveryStore store = new RecoveryStore(recovery, install);
        store.CommitPreviousInstaller(candidate, release);

        RecoveryValidation validation = store.ValidatePreviousInstaller();
        AssertTrue(validation.IsValid, "committed current installer valid");
        AssertEqual("2.4.7", validation.Metadata.previous_version, "committed version");
        AssertFalse(File.Exists(candidate), "candidate moved into cache");
    }

    private static void TestRollbackSafety(string root)
    {
        AssertTrue(RollbackWorker.IsCleanupTarget("_internal"), "runtime cleanup allowed");
        AssertTrue(RollbackWorker.IsCleanupTarget("ClaudeApp.exe"), "app cleanup allowed");
        AssertFalse(RollbackWorker.IsCleanupTarget("drivers"), "driver preserved");
        AssertFalse(RollbackWorker.IsCleanupTarget("user-data"), "unknown directory preserved");
        AssertFalse(RollbackWorker.IsSafeInstallDirectory(Path.GetPathRoot(root)), "filesystem root rejected");
        string install = Path.Combine(root, "SafeInstall");
        Directory.CreateDirectory(install);
        File.WriteAllText(Path.Combine(install, "version.txt"), "2.4.7");
        AssertTrue(RollbackWorker.IsSafeInstallDirectory(install), "versioned install accepted");
    }

    private static void TestRecoveryFormButtons(string root)
    {
        RecoveryStore store = new RecoveryStore(Path.Combine(root, "FormRecovery"), Path.Combine(root, "FormInstall"));
        Directory.CreateDirectory(store.RecoveryRoot);
        Directory.CreateDirectory(store.InstallDirectory);
        using (RecoveryForm form = new RecoveryForm(
            new CrashInfo { kind = "BOOT", message = "QtWidgets failure", traceback = "trace", exit_code = 1 },
            store,
            "2.4.7"))
        {
            HashSet<string> labels = new HashSet<string>();
            foreach (Control control in form.Controls)
                CollectButtonLabels(control, labels);
            AssertTrue(labels.Contains("이전 버전으로 되돌리기"), "rollback button");
            AssertTrue(labels.Contains("업데이트 확인"), "update button");
            AssertTrue(labels.Contains("오류 내용 복사"), "copy button");
            AssertTrue(labels.Contains("닫기"), "close button");
        }
    }

    private static void CollectButtonLabels(Control parent, HashSet<string> labels)
    {
        Button button = parent as Button;
        if (button != null) labels.Add(button.Text);
        foreach (Control child in parent.Controls) CollectButtonLabels(child, labels);
    }

    [STAThread]
    public static int Main()
    {
        string root = Path.Combine(Path.GetTempPath(), "ClaudeRecoveryTests-" + Guid.NewGuid().ToString("N"));
        try
        {
            TestLaunchDecision();
            TestRecoveryStoreValidation(root);
            TestMalformedCrashIsSafe(root);
            TestUpdatePolicyAndUrl();
            TestCommitPreviousInstaller(root);
            TestRollbackSafety(root);
            TestRecoveryFormButtons(root);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("UNHANDLED_TYPE " + error.GetType().FullName);
            Console.Error.WriteLine("UNHANDLED_MESSAGE " + error.Message);
            Console.Error.WriteLine("UNHANDLED_STACK " + error.StackTrace);
            _failures++;
        }
        finally
        {
            try
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
            catch (Exception error)
            {
                Console.Error.WriteLine("CLEANUP_TYPE " + error.GetType().FullName);
                Console.Error.WriteLine("CLEANUP_MESSAGE " + error.Message);
                Console.Error.WriteLine("CLEANUP_STACK " + error.StackTrace);
                _failures++;
            }
        }
        if (_failures != 0) return 1;
        Console.WriteLine("PASS");
        return 0;
    }
}
