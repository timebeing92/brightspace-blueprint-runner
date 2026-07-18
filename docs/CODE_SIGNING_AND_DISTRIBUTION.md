# Code Signing And Distribution Decision

Status: the v2.8.0 managed and portable ZIPs are intentionally unsigned and
not notarized. That is acceptable for the current small, named internal user
group when the trust prompts are disclosed and institutional policy permits
continuation. Signing should be treated as a release gate before broad
distribution to nontechnical or externally managed users.

## What signing changes

The launcher's manifest, commit receipts, GitHub asset digest, and SHA-256
sidecars prove that a downloaded release matches what this project published.
Operating-system signing adds a different assurance: macOS or Windows can show
the verified publisher and detect modification before the user trusts the
download. These protections complement one another; checksums do not replace
publisher identity, and signing does not replace release provenance.

## macOS

Apple's direct-distribution path uses a Developer ID certificate plus Apple
notarization. Gatekeeper can then verify the publisher, notarization ticket,
and whether the software was altered or is known malware. Notarization is an
automated security/signature check, not Mac App Store review.

The current launch surface is a `.command` shell script and a directory of
Python source, not a conventional macOS `.app`. For a polished signed release,
the cleanest approach is therefore likely one of:

1. Wrap the durable launcher in a minimal macOS `.app`, sign it with a
   Developer ID Application certificate, enable the required hardened-runtime
   settings, notarize the distribution, and staple the ticket where supported.
2. Deliver the signed launcher and managed tree through a signed flat `.pkg`
   using a Developer ID Installer certificate, then notarize the package.

Trying to describe the loose ZIP itself as “signed” would be misleading. The
executable launch surface and any bundled executable code must meet Apple's
requirements, and the final distributable must be submitted to the notary
service with `notarytool` or the Notary API.

Official references:

- https://developer.apple.com/help/account/certificates/create-developer-id-certificates/
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://developer.apple.com/documentation/security/customizing-the-notarization-workflow

## Windows

SmartScreen considers both publisher reputation and the downloaded file's
reputation. A trusted signature gives Windows a stable publisher identity and
shows that the signed artifact was not changed, but a new signed build may
still receive an “unrecognized app” warning while reputation develops. Current
Microsoft guidance says EV certificates no longer provide an automatic
first-download SmartScreen bypass.

Windows 11 Smart App Control can be stricter: unknown unsigned executable code
may be blocked unless Microsoft's intelligence already considers it safe. A
self-signed certificate is suitable only for development or for an
institution whose IT administrators deploy that certificate as trusted.

The current Windows entry point is a batch file delegating to PowerShell. For
wider distribution, a signed native bootstrap executable, signed MSI/MSIX, or
other signed installer is a clearer trust surface than a loose unsigned ZIP of
scripts. Microsoft recommends Artifact Signing for non-Store production
distribution; a conventional organization-validated certificate from a
trusted certificate authority is another option. Microsoft Store distribution
would avoid download warnings most reliably, but it is a materially different
packaging and publication model.

Official references:

- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/en-us/azure/artifact-signing/
- https://learn.microsoft.com/en-us/windows/msix/package/sign-app-package-using-signtool

## Recommended threshold

| Distribution scope | Recommended posture |
| --- | --- |
| Maintainer fixtures and local automation | Unsigned is acceptable; verify commits, manifests, and hashes. |
| Small, named internal review group | Unsigned review kit is acceptable if warnings are disclosed, testers know the source, institutional policy permits continuation, and nobody weakens system-wide security. |
| Department-wide pilot | Prefer signing; coordinate with IT first because managed-device policy can block unsigned scripts regardless of instructions. |
| Broad public or cross-institution distribution | Treat signed native launch surfaces plus macOS notarization as a release requirement. |

## Implementation boundary

Signing credentials must never live in the repository or a release ZIP. A
future signing pipeline should:

1. Produce the deterministic unsigned runner/bundle release and record its
   identities and hash.
2. Build the small platform-specific launcher or installer around that exact
   release.
3. Sign through protected CI secrets, a managed signing service, or appropriate
   key hardware.
4. Timestamp signatures, notarize the macOS deliverable, and retain the notary
   request/log or Windows certificate thumbprint in the release receipt.
5. Verify the final signed artifacts on clean macOS and Windows machines before
   publication.
6. Publish final signed-artifact hashes; never modify an artifact after it is
   signed.

The stable updater also needs an explicit policy for signed future payloads.
Its current GitHub identity and checksum checks are strong transport/release
controls, but a signed-release phase should add platform-signature verification
without weakening those existing checks.
