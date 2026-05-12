package com.emrtd.reader.nfc

import android.nfc.tech.IsoDep
import android.util.Log
import com.emrtd.reader.model.*
import net.sf.scuba.smartcards.CardService
import org.jmrtd.BACKey
import org.jmrtd.PassportService
import org.jmrtd.lds.SODFile
import org.jmrtd.lds.icao.*
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.security.SecureRandom

class PassportReader {

    companion object {
        private const val TAG = "PassportReader"
    }

    @Suppress("BlockingMethodInNonBlockingContext")
    suspend fun readPassport(isoDep: IsoDep, mrzData: MrzData): EmrtdResult {
        isoDep.timeout = 15_000

        val cardService = CardService.getInstance(isoDep)
        var passportService: PassportService? = null

        val dataGroups = mutableMapOf<String, Boolean>()
        val dgHashes = mutableMapOf<String, String>()  // dgNum -> hex hash
        var personalData: PersonalData? = null
        var mrzInfo: MrzInfo? = null
        var rawSodHex: String? = null
        var aaPublicKeyHex: String? = null
        var aaChallengeHex: String? = null
        var aaResponseHex: String? = null
        var aaAlgorithm: String? = null
        var chipAuthPublicKeyHex: String? = null
        var chipAuthOid: String? = null

        val bacKey = BACKey(
            mrzData.documentNumber,
            mrzData.dateOfBirth,
            mrzData.dateOfExpiry
        )

        try {
            cardService.open()
            passportService = PassportService(
                cardService,
                PassportService.NORMAL_MAX_TRANCEIVE_LENGTH,
                PassportService.DEFAULT_MAX_BLOCKSIZE,
                false,
                false
            )
            passportService.open()

            // ── PACE / BAC ───────────────────────────────────────────────
            var paceSuccess = false
            var bacSuccess = false
            var paceError: String? = null
            var bacError: String? = null
            var authMethod = "none"

            try {
                val paceKey = org.jmrtd.PACEKeySpec.createMRZKey(bacKey)
                passportService.doPACE(paceKey, PassportService.MF, null, null)
                paceSuccess = true
                authMethod = "PACE"
                Log.i(TAG, "PACE succeeded")
            } catch (e: Exception) {
                paceError = e.message
                Log.i(TAG, "PACE failed (${e.message}), trying BAC")
                try {
                    passportService.doBAC(bacKey)
                    bacSuccess = true
                    authMethod = "BAC"
                    Log.i(TAG, "BAC succeeded")
                } catch (bex: Exception) {
                    bacError = bex.message
                    Log.e(TAG, "BAC also failed: ${bex.message}")
                }
            }

            if (!paceSuccess && !bacSuccess) {
                return EmrtdResult(
                    mrzInfo = null, personalData = null,
                    securityChecks = SecurityChecks(
                        bacOrPacePerformed = authMethod,
                        paceError = paceError, bacError = bacError
                    ),
                    dataGroups = dataGroups, rawSodHex = null,
                    dgHashesHex = dgHashes, aaPublicKeyHex = null,
                    aaChallengeHex = null, aaResponseHex = null, aaAlgorithm = null,
                    chipAuthPublicKeyHex = null, chipAuthOid = null,
                    error = "Authentication failed — PACE: $paceError | BAC: $bacError"
                )
            }

            // ── Read SOD ─────────────────────────────────────────────────────
            var sodFile: SODFile? = null
            var hashAlg = "SHA-256"
            try {
                val sodBytes = passportService.getInputStream(PassportService.EF_SOD).readAllBytes()
                sodFile = SODFile(sodBytes.inputStream())
                rawSodHex = sodBytes.toHexString()
                hashAlg = sodFile.digestAlgorithm
                Log.i(TAG, "SOD read OK, hash alg: $hashAlg")
            } catch (e: Exception) {
                Log.e(TAG, "SOD read failed: ${e.message}")
            }

            // ── Read Data Groups ──────────────────────────────────────────
            val dgFileIds = mapOf(
                1 to PassportService.EF_DG1,
                2 to PassportService.EF_DG2,
                3 to PassportService.EF_DG3,
                4 to PassportService.EF_DG4,
                5 to PassportService.EF_DG5,
                6 to PassportService.EF_DG6,
                7 to PassportService.EF_DG7,
                8 to PassportService.EF_DG8,
                9 to PassportService.EF_DG9,
                10 to PassportService.EF_DG10,
                11 to PassportService.EF_DG11,
                12 to PassportService.EF_DG12,
                13 to PassportService.EF_DG13,
                14 to PassportService.EF_DG14,
                15 to PassportService.EF_DG15
            )

            for ((dgNum, fid) in dgFileIds) {
                val dgName = "DG$dgNum"
                try {
                    val bytes = passportService.getInputStream(fid).readAllBytes()
                    dataGroups[dgName] = true

                    // Compute hash for Passive Auth
                    val md = MessageDigest.getInstance(hashAlg)
                    dgHashes[dgNum.toString()] = md.digest(bytes).toHexString()

                    // Parse DG1 for personal data
                    if (dgNum == 1) {
                        val dg1 = DG1File(bytes.inputStream())
                        val mrz = dg1.mrzInfo
                        mrzInfo = MrzInfo(
                            documentNumber = mrz.documentNumber ?: "",
                            dateOfBirth = mrz.dateOfBirth ?: "",
                            dateOfExpiry = mrz.dateOfExpiry ?: "",
                            surname = mrz.secondaryIdentifier ?: "",
                            givenNames = mrz.primaryIdentifier ?: "",
                            nationality = mrz.nationality ?: "",
                            sex = mrz.gender?.toString() ?: "",
                            issuingCountry = mrz.issuingState ?: ""
                        )
                        personalData = PersonalData(
                            surname = mrz.secondaryIdentifier ?: "",
                            givenNames = mrz.primaryIdentifier ?: "",
                            nationality = mrz.nationality ?: "",
                            dateOfBirth = mrz.dateOfBirth ?: "",
                            sex = mrz.gender?.toString() ?: "",
                            dateOfExpiry = mrz.dateOfExpiry ?: "",
                            documentNumber = mrz.documentNumber ?: "",
                            issuingCountry = mrz.issuingState ?: "",
                            optionalData = mrz.optionalData1 ?: ""
                        )
                    }

                    // Parse DG14 for Chip Auth
                    if (dgNum == 14) {
                        try {
                            val dg14 = DG14File(bytes.inputStream())
                            for (si in dg14.securityInfos) {
                                if (si is org.jmrtd.lds.ChipAuthenticationPublicKeyInfo) {
                                    val pubKey = si.subjectPublicKey
                                    chipAuthPublicKeyHex = pubKey.encoded.toHexString()
                                    chipAuthOid = si.objectIdentifier
                                    break
                                }
                            }
                        } catch (e: Exception) {
                            Log.w(TAG, "DG14 parse: ${e.message}")
                        }
                    }

                    // Parse DG15 for Active Auth
                    if (dgNum == 15) {
                        try {
                            val dg15 = DG15File(bytes.inputStream())
                            aaPublicKeyHex = dg15.publicKey.encoded.toHexString()
                        } catch (e: Exception) {
                            Log.w(TAG, "DG15 parse: ${e.message}")
                        }
                    }

                    Log.i(TAG, "$dgName read OK (${bytes.size} bytes)")
                } catch (e: Exception) {
                    dataGroups[dgName] = false
                    Log.d(TAG, "$dgName not available: ${e.message}")
                }
            }

            // ── Passive Authentication (on-device pre-check) ──────────────────
            var passiveAuthSuccess = false
            var passiveAuthError: String? = null
            if (sodFile != null) {
                try {
                    val storedHashes = sodFile.dataGroupHashes
                    var allMatch = true
                    for ((dgNum, storedHash) in storedHashes) {
                        val computed = dgHashes[dgNum.toString()]
                        if (computed != null && computed != storedHash.toHexString()) {
                            allMatch = false
                            Log.w(TAG, "DG$dgNum hash mismatch")
                        }
                    }
                    passiveAuthSuccess = allMatch
                    if (!allMatch) passiveAuthError = "DG hash mismatch detected"
                } catch (e: Exception) {
                    passiveAuthError = e.message
                    Log.e(TAG, "Passive auth: ${e.message}")
                }
            } else {
                passiveAuthError = "SOD not available"
            }

            // ── Active Authentication ───────────────────────────────────────────
            var activeAuthSuccess = false
            var activeAuthError: String? = null
            if (aaPublicKeyHex != null) {
                try {
                    val challenge = ByteArray(8).also { SecureRandom().nextBytes(it) }
                    aaChallengeHex = challenge.toHexString()

                    val pubKey = android.security.keystore.KeyGenParameterSpec.Builder("", 0).build().let {
                        null
                    } ?: run {
                        val dg15 = DG15File(passportService.getInputStream(PassportService.EF_DG15))
                        dg15.publicKey
                    }

                    val keyAlg = pubKey.algorithm
                    val sigAlg = if (keyAlg == "EC") "SHA256WithECDSA" else "SHA256WithRSA"
                    aaAlgorithm = sigAlg

                    val aaResult = passportService.doAA(pubKey, "SHA-256", sigAlg, challenge)
                    aaResponseHex = aaResult.response.toHexString()
                    activeAuthSuccess = true
                    Log.i(TAG, "Active Authentication succeeded")
                } catch (e: Exception) {
                    activeAuthError = e.message
                    Log.e(TAG, "Active auth: ${e.message}")
                }
            } else {
                activeAuthError = "DG15 not available"
            }

            // ── Chip Authentication ───────────────────────────────────────────
            var chipAuthSuccess = false
            var chipAuthError: String? = null
            if (chipAuthPublicKeyHex != null && chipAuthOid != null) {
                try {
                    val dg14 = DG14File(passportService.getInputStream(PassportService.EF_DG14))
                    for (si in dg14.securityInfos) {
                        if (si is org.jmrtd.lds.ChipAuthenticationPublicKeyInfo) {
                            passportService.doEACCA(
                                si.keyId,
                                si.subjectPublicKey.algorithm,
                                si.objectIdentifier,
                                si.subjectPublicKey
                            )
                            chipAuthSuccess = true
                            Log.i(TAG, "Chip Authentication succeeded")
                            break
                        }
                    }
                    if (!chipAuthSuccess) chipAuthError = "No CA key info found in DG14"
                } catch (e: Exception) {
                    chipAuthError = e.message
                    Log.d(TAG, "Chip auth: ${e.message}")
                }
            } else {
                chipAuthError = "DG14 not available or no CA key info"
            }

            return EmrtdResult(
                mrzInfo = mrzInfo,
                personalData = personalData,
                securityChecks = SecurityChecks(
                    bacSuccess = bacSuccess,
                    paceSuccess = paceSuccess,
                    bacOrPacePerformed = authMethod,
                    passiveAuthSuccess = passiveAuthSuccess,
                    activeAuthSuccess = activeAuthSuccess,
                    chipAuthSuccess = chipAuthSuccess,
                    eacSuccess = false,
                    bacError = bacError,
                    paceError = paceError,
                    passiveAuthError = passiveAuthError,
                    activeAuthError = activeAuthError,
                    chipAuthError = chipAuthError,
                    eacError = "EAC not performed (requires country CVCA certificates)"
                ),
                dataGroups = dataGroups,
                rawSodHex = rawSodHex,
                dgHashesHex = dgHashes,
                aaPublicKeyHex = aaPublicKeyHex,
                aaChallengeHex = aaChallengeHex,
                aaResponseHex = aaResponseHex,
                aaAlgorithm = aaAlgorithm,
                chipAuthPublicKeyHex = chipAuthPublicKeyHex,
                chipAuthOid = chipAuthOid
            )

        } catch (e: Exception) {
            Log.e(TAG, "Passport reading failed: ${e.message}", e)
            return EmrtdResult(
                mrzInfo = null, personalData = null,
                securityChecks = SecurityChecks(),
                dataGroups = dataGroups,
                rawSodHex = rawSodHex,
                dgHashesHex = dgHashes,
                aaPublicKeyHex = null, aaChallengeHex = null,
                aaResponseHex = null, aaAlgorithm = null,
                chipAuthPublicKeyHex = null, chipAuthOid = null,
                error = e.message
            )
        } finally {
            try { passportService?.close() } catch (_: Exception) {}
            try { cardService.close() } catch (_: Exception) {}
        }
    }

    private fun java.io.InputStream.readAllBytes(): ByteArray {
        val buf = ByteArrayOutputStream()
        val tmp = ByteArray(4096)
        var n: Int
        while (read(tmp).also { n = it } != -1) buf.write(tmp, 0, n)
        return buf.toByteArray()
    }

    private fun ByteArray.toHexString() = joinToString("") { "%02x".format(it) }
}
