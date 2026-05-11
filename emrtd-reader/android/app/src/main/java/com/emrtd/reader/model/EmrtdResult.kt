package com.emrtd.reader.model

data class EmrtdResult(
    val mrzInfo: MrzInfo?,
    val personalData: PersonalData?,
    val securityChecks: SecurityChecks,
    val dataGroups: Map<String, Boolean>,
    val rawSodHex: String?,
    val dgHashesHex: Map<String, String>,
    val aaPublicKeyHex: String?,
    val aaChallengeHex: String?,
    val aaResponseHex: String?,
    val aaAlgorithm: String?,
    val chipAuthPublicKeyHex: String?,
    val chipAuthOid: String?,
    val error: String? = null
)

data class MrzInfo(
    val documentNumber: String,
    val dateOfBirth: String,
    val dateOfExpiry: String,
    val surname: String,
    val givenNames: String,
    val nationality: String,
    val sex: String,
    val issuingCountry: String
)

data class PersonalData(
    val surname: String,
    val givenNames: String,
    val nationality: String,
    val dateOfBirth: String,
    val sex: String,
    val dateOfExpiry: String,
    val documentNumber: String,
    val issuingCountry: String,
    val optionalData: String
)

data class SecurityChecks(
    val bacSuccess: Boolean = false,
    val paceSuccess: Boolean = false,
    val bacOrPacePerformed: String = "none",
    val passiveAuthSuccess: Boolean = false,
    val activeAuthSuccess: Boolean = false,
    val chipAuthSuccess: Boolean = false,
    val eacSuccess: Boolean = false,
    val bacError: String? = null,
    val paceError: String? = null,
    val passiveAuthError: String? = null,
    val activeAuthError: String? = null,
    val chipAuthError: String? = null,
    val eacError: String? = null
)
