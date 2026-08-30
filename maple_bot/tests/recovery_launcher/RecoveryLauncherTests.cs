// 복구 실행기의 종료 판정과 저장소 무결성을 실제 C# 코드로 검증한다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

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

    public static int Main()
    {
        string root = Path.Combine(Path.GetTempPath(), "ClaudeRecoveryTests-" + Guid.NewGuid().ToString("N"));
        try
        {
            TestLaunchDecision();
            TestRecoveryStoreValidation(root);
            TestMalformedCrashIsSafe(root);
        }
        finally
        {
            if (Directory.Exists(root)) Directory.Delete(root, true);
        }
        if (_failures != 0) return 1;
        Console.WriteLine("PASS");
        return 0;
    }
}
