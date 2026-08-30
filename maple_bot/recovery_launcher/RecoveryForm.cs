// 치명적 오류 상세와 이전 버전 복원·업데이트·복사·닫기 기능을 제공한다.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal sealed class RecoveryForm : Form
{
    private readonly CrashInfo _crash;
    private readonly RecoveryStore _store;
    private readonly string _currentVersion;
    private readonly UpdateClient _updates = new UpdateClient();
    private readonly TextBox _details = new TextBox();
    private readonly Label _status = new Label();
    private readonly Button _rollback = new Button();
    private readonly Button _update = new Button();
    private readonly Button _copy = new Button();
    private readonly Button _close = new Button();

    internal RecoveryForm(CrashInfo crash, RecoveryStore store, string currentVersion)
    {
        _crash = crash ?? new CrashInfo { kind = "UNKNOWN", message = "알 수 없는 오류입니다." };
        _store = store;
        _currentVersion = string.IsNullOrWhiteSpace(currentVersion) ? "0.0.0" : currentVersion.Trim();
        BuildUi();
        ConfigureRollback();
    }

    private void BuildUi()
    {
        Text = "Claude 복구";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(720, 480);
        Size = new Size(760, 540);
        Font = new Font("Malgun Gothic", 9F);

        TableLayoutPanel layout = new TableLayoutPanel();
        layout.Dock = DockStyle.Fill;
        layout.Padding = new Padding(16);
        layout.RowCount = 4;
        layout.ColumnCount = 1;
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        Label title = new Label();
        title.AutoSize = true;
        title.Font = new Font(Font, FontStyle.Bold);
        title.Text = "Claude가 비정상 종료되었습니다.\r\n" + (_crash.message ?? "상세 오류가 없습니다.");
        title.Margin = new Padding(0, 0, 0, 10);
        layout.Controls.Add(title, 0, 0);

        _details.Dock = DockStyle.Fill;
        _details.Multiline = true;
        _details.ReadOnly = true;
        _details.ScrollBars = ScrollBars.Both;
        _details.WordWrap = false;
        _details.Font = new Font("Consolas", 9F);
        _details.Text = BuildErrorText();
        layout.Controls.Add(_details, 0, 1);

        _status.AutoSize = true;
        _status.MaximumSize = new Size(700, 0);
        _status.Margin = new Padding(0, 10, 0, 8);
        layout.Controls.Add(_status, 0, 2);

        FlowLayoutPanel buttons = new FlowLayoutPanel();
        buttons.Dock = DockStyle.Fill;
        buttons.AutoSize = true;
        buttons.FlowDirection = FlowDirection.LeftToRight;
        buttons.WrapContents = false;
        _rollback.Text = "이전 버전으로 되돌리기";
        _rollback.AutoSize = true;
        _update.Text = "업데이트 확인";
        _update.AutoSize = true;
        _copy.Text = "오류 내용 복사";
        _copy.AutoSize = true;
        _close.Text = "닫기";
        _close.AutoSize = true;
        buttons.Controls.Add(_rollback);
        buttons.Controls.Add(_update);
        buttons.Controls.Add(_copy);
        buttons.Controls.Add(_close);
        layout.Controls.Add(buttons, 0, 3);
        Controls.Add(layout);

        _rollback.Click += delegate { StartRollback(); };
        _update.Click += delegate { StartUpdateCheck(); };
        _copy.Click += delegate { Clipboard.SetText(_details.Text); _status.Text = "오류 내용을 복사했습니다."; };
        _close.Click += delegate { Close(); };
    }

    private string BuildErrorText()
    {
        StringBuilder text = new StringBuilder();
        text.AppendLine("종류: " + (_crash.kind ?? "UNKNOWN"));
        text.AppendLine("단계: " + _crash.phase);
        text.AppendLine("종료 코드: " + _crash.exit_code);
        text.AppendLine("시각: " + (_crash.created_at ?? string.Empty));
        text.AppendLine();
        text.AppendLine(_crash.message ?? string.Empty);
        if (!string.IsNullOrWhiteSpace(_crash.traceback))
        {
            text.AppendLine();
            text.AppendLine(_crash.traceback);
        }
        return text.ToString();
    }

    private void ConfigureRollback()
    {
        RecoveryValidation validation = _store.ValidatePreviousInstaller();
        _rollback.Enabled = validation.IsValid;
        _status.Text = validation.IsValid
            ? "이전 버전 " + validation.Metadata.previous_version + " 복구 파일을 사용할 수 있습니다."
            : "이전 버전 복구 불가: " + validation.Reason;
    }

    private void SetBusy(bool busy)
    {
        _rollback.Enabled = !busy && _store.ValidatePreviousInstaller().IsValid;
        _update.Enabled = !busy;
        _copy.Enabled = !busy;
        _close.Enabled = true;
    }

    private void StartRollback()
    {
        try
        {
            SetBusy(true);
            _status.Text = "이전 버전 복구 작업자를 시작합니다.";
            RollbackWorker.StartDetached(_store);
            Close();
        }
        catch (Exception error)
        {
            SetBusy(false);
            _status.Text = "이전 버전 복구 실패: " + error.Message;
        }
    }

    private void StartUpdateCheck()
    {
        SetBusy(true);
        _status.Text = "업데이트 정보를 확인하는 중입니다.";
        ThreadPool.QueueUserWorkItem(delegate
        {
            try
            {
                ReleaseInfo latest = _updates.FetchLatest();
                UpdateAction action = UpdatePolicy.Decide(_currentVersion, latest.version);
                if (action == UpdateAction.None)
                    throw new InvalidOperationException("설치 가능한 최신 버전이 없습니다.");
                if (action == UpdateAction.Update)
                {
                    ReleaseInfo current = _store.ReadLocalRelease();
                    string currentSetup = _updates.DownloadVerified(current, _store.RecoveryRoot, null);
                    _store.CommitPreviousInstaller(currentSetup, current);
                }
                string downloadDirectory = Path.Combine(Path.GetTempPath(), "ClaudeUpdate");
                string latestSetup = _updates.DownloadVerified(latest, downloadDirectory, ReportProgress);
                ProcessStartInfo start = new ProcessStartInfo(latestSetup);
                start.UseShellExecute = true;
                start.Arguments = "/DIR=\"" + _store.InstallDirectory.Replace("\"", "\\\"") + "\"";
                Process process = Process.Start(start);
                if (process == null) throw new InvalidOperationException("업데이트 설치기를 시작하지 못했습니다.");
                BeginInvoke(new Action(Close));
            }
            catch (Exception error)
            {
                BeginInvoke(new Action(delegate
                {
                    SetBusy(false);
                    _status.Text = "업데이트 실패: " + error.Message;
                }));
            }
        });
    }

    private void ReportProgress(long downloaded, long total)
    {
        if (!IsHandleCreated || IsDisposed) return;
        BeginInvoke(new Action(delegate
        {
            if (total > 0)
                _status.Text = "업데이트 다운로드 중 " + downloaded / 1048576 + " MB / " + total / 1048576 + " MB";
            else
                _status.Text = "업데이트 다운로드 중 " + downloaded / 1048576 + " MB";
        }));
    }
}
