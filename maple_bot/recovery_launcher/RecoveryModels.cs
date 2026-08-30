// 복구 상태 JSON 모델과 실제 앱 종료 판정 값을 정의한다.
using System;

internal enum FailurePhase
{
    Startup,
    Runtime
}

internal static class LaunchDecision
{
    internal static bool ShouldShowRecovery(int exitCode, bool readySeen, bool normalMarkerSeen)
    {
        if (normalMarkerSeen) return false;
        return exitCode != 0;
    }

    internal static FailurePhase GetFailurePhase(bool readySeen)
    {
        return readySeen ? FailurePhase.Runtime : FailurePhase.Startup;
    }
}

internal sealed class RecoveryMetadata
{
    public string previous_version { get; set; }
    public string current_version { get; set; }
    public string installation_path { get; set; }
    public string previous_sha256 { get; set; }
    public string created_at { get; set; }
}

internal sealed class ReleaseInfo
{
    public string version { get; set; }
    public string notes { get; set; }
    public string download_url { get; set; }
    public string sha256 { get; set; }
}

internal sealed class CrashInfo
{
    public string kind { get; set; }
    public string message { get; set; }
    public string traceback { get; set; }
    public int exit_code { get; set; }
    public int pid { get; set; }
    public string created_at { get; set; }
    public FailurePhase phase { get; set; }
}

internal sealed class RecoveryValidation
{
    internal bool IsValid { get; private set; }
    internal string Reason { get; private set; }
    internal string InstallerPath { get; private set; }
    internal RecoveryMetadata Metadata { get; private set; }

    internal static RecoveryValidation Valid(string installerPath, RecoveryMetadata metadata)
    {
        return new RecoveryValidation
        {
            IsValid = true,
            Reason = string.Empty,
            InstallerPath = installerPath,
            Metadata = metadata
        };
    }

    internal static RecoveryValidation Invalid(string reason)
    {
        return new RecoveryValidation
        {
            IsValid = false,
            Reason = reason ?? "복구 파일을 사용할 수 없습니다.",
            InstallerPath = string.Empty,
            Metadata = null
        };
    }
}

internal sealed class RecoveryRunPaths
{
    internal string ReadyFile { get; set; }
    internal string CrashFile { get; set; }
    internal string NormalFile { get; set; }
}
