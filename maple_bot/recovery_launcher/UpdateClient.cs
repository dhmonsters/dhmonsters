// 복구창에서 공식 업데이트 정보를 조회하고 설치 파일을 해시 검증해 내려받는다.
using System;
using System.IO;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

internal sealed class UpdateClient
{
    private const string VersionUrl = "https://raw.githubusercontent.com/dhmonsters/dhmonsters/main/maple_bot/version.json";
    private static readonly Regex Sha256Pattern = new Regex("^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant);

    internal static bool IsAllowedReleaseUrl(string value)
    {
        Uri uri;
        if (!Uri.TryCreate(value, UriKind.Absolute, out uri)) return false;
        return uri.Scheme == Uri.UriSchemeHttps
            && string.Equals(uri.Host, "github.com", StringComparison.OrdinalIgnoreCase)
            && uri.AbsolutePath.StartsWith(
                "/dhmonsters/dhmonsters/releases/download/", StringComparison.Ordinal);
    }

    internal static void ValidateRelease(ReleaseInfo release)
    {
        if (release == null) throw new InvalidDataException("업데이트 정보가 없습니다.");
        if (string.IsNullOrWhiteSpace(release.version)) throw new InvalidDataException("version이 없습니다.");
        if (!IsAllowedReleaseUrl(release.download_url)) throw new InvalidDataException("공식 GitHub Release URL이 아닙니다.");
        release.sha256 = (release.sha256 ?? string.Empty).Trim().ToLowerInvariant();
        if (!Sha256Pattern.IsMatch(release.sha256)) throw new InvalidDataException("sha256이 올바르지 않습니다.");
    }

    internal ReleaseInfo FetchLatest()
    {
        HttpWebRequest request = (HttpWebRequest)WebRequest.Create(VersionUrl);
        request.Timeout = 10000;
        request.ReadWriteTimeout = 10000;
        request.UserAgent = "Claude-Recovery-Launcher";
        using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
        using (Stream stream = response.GetResponseStream())
        using (StreamReader reader = new StreamReader(stream, Encoding.UTF8, true))
        {
            ReleaseInfo release = new JavaScriptSerializer().Deserialize<ReleaseInfo>(reader.ReadToEnd());
            ValidateRelease(release);
            return release;
        }
    }

    internal string DownloadVerified(ReleaseInfo release, string destinationDirectory, Action<long, long> progress)
    {
        ValidateRelease(release);
        Directory.CreateDirectory(destinationDirectory);
        string destination = Path.Combine(destinationDirectory, "Claude_update_setup.exe");
        if (File.Exists(destination)) File.Delete(destination);
        try
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(release.download_url);
            request.Timeout = 30000;
            request.ReadWriteTimeout = 30000;
            request.UserAgent = "Claude-Recovery-Launcher";
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            using (Stream input = response.GetResponseStream())
            using (FileStream output = File.Create(destination))
            {
                byte[] buffer = new byte[65536];
                long written = 0;
                int count;
                while ((count = input.Read(buffer, 0, buffer.Length)) > 0)
                {
                    output.Write(buffer, 0, count);
                    written += count;
                    if (progress != null) progress(written, response.ContentLength);
                }
            }
            string actual = RecoveryStore.ComputeSha256(destination);
            if (!string.Equals(actual, release.sha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("다운로드한 설치 파일의 SHA-256이 일치하지 않습니다.");
            return destination;
        }
        catch
        {
            try { if (File.Exists(destination)) File.Delete(destination); } catch { }
            throw;
        }
    }
}
