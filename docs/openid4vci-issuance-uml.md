# OpenID4VCI Issuance Flow

The following UML sequence diagram captures the end-to-end interactions between the main actors in an OpenID for Verifiable Credential Issuance (OpenID4VCI) exchange, starting from a credential offer and covering both the pre-authorized and OAuth 2.0 authorization code grant options.

```mermaid
sequenceDiagram
    autonumber
    actor HolderWallet as Holder Wallet
    participant CredentialIssuer as Credential Issuer
    participant AuthorizationServer as Authorization Server / Token Endpoint
    participant CredentialEndpoint as Credential Endpoint

    HolderWallet->>CredentialIssuer: Receive credential_offer (QR / deep link / redirect)
    note over HolderWallet,CredentialIssuer: Offer contains credential_configuration_ids and optionally a pre-authorized_code

    HolderWallet->>CredentialIssuer: Resolve issuer metadata (.well-known/openid-credential-issuer)
    CredentialIssuer-->>HolderWallet: Issuer configuration (authorization_servers,<br/>credential_endpoint, batch endpoints)

    HolderWallet->>CredentialIssuer: Fetch credential metadata (credential_configuration_ids)
    CredentialIssuer-->>HolderWallet: Supported formats, grants, proof types, status mechanisms

    alt Pre-authorized Code Grant
        HolderWallet->>AuthorizationServer: Token request (pre-authorized_code,<br/>optional user PIN)
        AuthorizationServer-->>HolderWallet: Access token + c_nonce (if required) + expires_in
    else OAuth 2.0 Authorization Code Grant
        HolderWallet->>AuthorizationServer: PAR / authorization request (scope=openid_credential)
        AuthorizationServer-->>HolderWallet: Authorization response (authorization_code)
        HolderWallet->>AuthorizationServer: Token request (authorization_code + client auth)
        AuthorizationServer-->>HolderWallet: Access token + c_nonce (if required) + refresh_token?
    end

    HolderWallet->>CredentialEndpoint: Credential request (format, proof of possession, access token,
        credential_definition)
    CredentialEndpoint-->>HolderWallet: Verifiable Credential (and optional c_nonce for follow-up proofs)

    opt Deferred / Batch Issuance
        HolderWallet->>CredentialEndpoint: Status / batch request (deferred_credential_endpoint or batch endpoint)
        CredentialEndpoint-->>HolderWallet: Deferred credential result, status list, or additional credentials
    end

    HolderWallet->>HolderWallet: Store credential, update wallet status, prepare presentations
```

## Actors and Artifacts

| Actor / Artifact | Description |
| --- | --- |
| **Holder Wallet** | Mobile or web wallet initiating issuance, managing keys, and storing credentials. |
| **Credential Issuer** | Entity exposing OpenID4VCI metadata, credential configurations, and issuance policies. |
| **Authorization Server** | OAuth 2.0 authorization and token endpoints used for grants. Might be shared across issuers. |
| **Credential Endpoint** | OpenID4VCI credential endpoint (and optional deferred/batch sub-resources) that returns the credential payload. |
| **Credential Offer** | JSON object or URI that bootstraps issuance, containing `credential_issuer`, supported `credential_configuration_ids`, and optionally a `pre-authorized_code` plus `user_pin_required`. |

## Flow Highlights

- **Offer bootstrap** introduces the wallet to the issuer, providing the issuer URL and credential configuration identifiers required to query metadata.
- **Metadata discovery** ensures the wallet learns about the issuer's capabilities, supported credentials, proof requirements, and authorization servers involved.
- **Authorization** can follow either the pre-authorized code path (e.g., via QR code) or a standard OAuth 2.0 authorization-code flow; both result in an access token and an optional `c_nonce` for proof of possession.
- **Credential issuance** occurs at the credential endpoint, where the wallet proves key possession (`proof` object, often JWT or SD-JWT) and requests specific credential configurations before receiving the final verifiable credential payload.
- **Deferred or batched issuance** may be needed when credentials are not immediately available; the wallet re-polls the deferred endpoint or requests additional credentials using the same access token when permitted.

## Implementation Notes

- Wallets should support **credential metadata caching** to avoid repeated metadata round-trips and detect updates via the issuer's cache headers or `cache_ttl` hints.
- Issuers can rotate `c_nonce` values and enforce **proof-of-possession binding** to the `access_token` to prevent replay attacks.
- For high-assurance flows, authorization servers may require **Dynamic Client Registration** or DPoP-bound access tokens; reflect this in the metadata and wallet support matrix.
- When multiple credential formats are available (e.g., SD-JWT, ISO mDL, or W3C VC), the wallet should negotiate via the `credential_configuration_id` and align proof types accordingly.
- Status endpoints (Status List 2021, Revocation List, or `status_list_credential`) should be surfaced in metadata so wallets can monitor credential validity post issuance.
