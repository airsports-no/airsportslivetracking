# MSFS client: crash reporting with Sentry

Status of `airsports-no/msfsclient` (WinUI 3, .NET 8), read on 2026-10-16:

* Sentry 6.12.0 is referenced, and `App.xaml.cs` (`StartCrashReporting`, `App_UnhandledException`) sends unhandled exceptions in
  **release builds only, and only when the environment variable `AIRSPORTS_SENTRY_DSN` is set**.
* Nothing sets that variable on a pilot's PC, so the shipped client reports nothing. The DSN has to be built into the release.
* The release string is `msfsclient@<version>` without the build number, and there is no environment tag, no user id and no symbol upload.

Crashlytics has no .NET SDK, so Sentry is the right tool for this client. The phone apps keep Crashlytics.

## 1. A Sentry project and its DSN

Create a project `msfs-client` (platform .NET) in the same Sentry organisation as the backend. Its DSN is not a secret in the
usual sense (it only allows sending events), so keep it as a GitHub **repository variable** `SENTRY_DSN` in `msfsclient`, not a secret.

## 2. Build the DSN into the release

`msfsclient/msfsclient.csproj`:

```xml
<ItemGroup>
  <AssemblyAttribute Include="System.Reflection.AssemblyMetadataAttribute" Condition="'$(SentryDsn)' != ''">
    <_Parameter1>SentryDsn</_Parameter1>
    <_Parameter2>$(SentryDsn)</_Parameter2>
  </AssemblyAttribute>
</ItemGroup>
```

`AppConfigService`: the environment variable (for a developer) wins, else the built-in value.

```csharp
var dsn = Environment.GetEnvironmentVariable("AIRSPORTS_SENTRY_DSN")
          ?? typeof(AppConfigService).Assembly.GetCustomAttributes<AssemblyMetadataAttribute>()
                 .FirstOrDefault(a => a.Key == "SentryDsn")?.Value;
CrashReportingDsn = string.IsNullOrWhiteSpace(dsn) ? null : dsn;
```

The build steps in `flightsim.yml` and `store.yml` pass it on: `-p:SentryDsn=${{ vars.SENTRY_DSN }}` (an empty value leaves
crash reporting off, as now).

## 3. A better init

```csharp
Sentry.SentrySdk.Init(o =>
{
    o.Dsn = dsn;
    o.Release = $"msfsclient@{config.AppVersion}+{config.BuildNumber}";   // the build the pilot installed
    o.Environment = config.IsTestMode ? "test" : "production";             // --base-url means a test server
    o.IsGlobalModeEnabled = true;
    o.SendDefaultPii = false;
    o.AutoSessionTracking = true;                                          // crash-free sessions per release
});
```

After sign-in, tag the reports with the pilot's Airsports user id (never the email), so a report can be matched to a support
request, and clear it on sign-out:

```csharp
Sentry.SentrySdk.ConfigureScope(s => s.User = new Sentry.SentryUser { Id = personId.ToString() });
```

Also report errors the app handles but that matter (a failed upload batch, SimConnect lost), so they show up without a crash:
`Sentry.SentrySdk.CaptureException(e)` in those catch blocks, or `CaptureMessage` for a state that is not an exception.
The existing local `crash.log` stays as the fallback for a pilot with no connection.

## 4. Readable stack traces (symbols)

Release builds need their `.pdb` files in Sentry. The Sentry NuGet package can upload them during the build:

```
dotnet publish ... -p:SentryUploadSymbols=true -p:SentryOrg=<org slug> -p:SentryProject=msfs-client
```

with `SENTRY_AUTH_TOKEN` in the step's environment. (Check the property names against the Sentry .NET MSBuild docs for the installed
package version; the alternative is `sentry-cli debug-files upload <publish folder>` after the build.) The build must keep the
portable `.pdb` (`<DebugType>portable</DebugType>`, the default for Release).

### The auth token

The backend uploads its JavaScript sourcemaps with a Sentry auth token (the Docker build secret `sentry_auth_token`, see the
`Dockerfile`). That secret is not in the GitHub secrets of `airsportslivetracking` (the list is empty), so it lives wherever the
production image is built. GitHub secrets are per repository, so `msfsclient` needs its own **`SENTRY_AUTH_TOKEN`** secret
(Settings > Secrets and variables > Actions), or an organisation secret shared by both repositories. A Sentry organisation
auth token with release and project-write scope works for both, so the same token can be reused. Never paste the token into a chat
or a file in a repository.

## 5. What to check

* A release build with the DSN set: throw a test exception (for example behind a hidden debug command) and see it in Sentry
  with the release `msfsclient@2.0.0+<build>` and a readable stack trace.
* A debug build and a build without the DSN send nothing.
* Add one line to the privacy text that crash reports (technical data, the Airsports user id, no names or emails) go to Sentry.
