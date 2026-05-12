package com.emrtd.reader.model

import com.google.gson.annotations.SerializedName

data class PersonalDataRequest(
    @SerializedName("surname") val surname: String?,
    @SerializedName("given_names") val givenNames: String?,
    @SerializedName("nationality") val nationality: String?,
    @SerializedName("date_of_birth") val dateOfBirth: String?,
    @SerializedName("sex") val sex: String?,
    @SerializedName("date_of_expiry") val dateOfExpiry: String?,
    @SerializedName("document_number") val documentNumber: String?,
    @SerializedName("issuing_country") val issuingCountry: String?,
    @SerializedName("optional_data") val optionalData: String? = null
)

data class EmrtdValidationRequest(
    @SerializedName("document_number") val documentNumber: String,
    @SerializedName("personal_data") val personalData: PersonalDataRequest?,
    @SerializedName("bac_or_pace_performed") val bacOrPacePerformed: String,
    @SerializedName("bac_success") val bacSuccess: Boolean,
    @SerializedName("pace_success") val paceSuccess: Boolean,
    @SerializedName("sod_bytes") val sodBytes: String?,
    @SerializedName("dg_hashes") val dgHashes: Map<String, String>?,
    @SerializedName("aa_public_key") val aaPublicKey: String?,
    @SerializedName("aa_challenge") val aaChallenge: String?,
    @SerializedName("aa_response") val aaResponse: String?,
    @SerializedName("aa_algorithm") val aaAlgorithm: String?,
    @SerializedName("chip_auth_public_key") val chipAuthPublicKey: String?,
    @SerializedName("chip_auth_oid") val chipAuthOid: String?,
    @SerializedName("data_groups_read") val dataGroupsRead: Map<String, Boolean>?
)

data class SecurityChecksResponse(
    @SerializedName("bac_or_pace_performed") val bacOrPacePerformed: String,
    @SerializedName("bac_success") val bacSuccess: Boolean,
    @SerializedName("pace_success") val paceSuccess: Boolean,
    @SerializedName("passive_auth_success") val passiveAuthSuccess: Boolean,
    @SerializedName("passive_auth_error") val passiveAuthError: String?,
    @SerializedName("active_auth_success") val activeAuthSuccess: Boolean,
    @SerializedName("active_auth_error") val activeAuthError: String?,
    @SerializedName("chip_auth_success") val chipAuthSuccess: Boolean,
    @SerializedName("chip_auth_error") val chipAuthError: String?,
    @SerializedName("eac_success") val eacSuccess: Boolean,
    @SerializedName("eac_error") val eacError: String?
)

data class EmrtdValidationResponse(
    @SerializedName("document_number") val documentNumber: String,
    @SerializedName("personal_data") val personalData: PersonalDataRequest?,
    @SerializedName("security_checks") val securityChecks: SecurityChecksResponse,
    @SerializedName("data_groups_read") val dataGroupsRead: Map<String, Boolean>,
    @SerializedName("overall_valid") val overallValid: Boolean,
    @SerializedName("validation_timestamp") val validationTimestamp: String
)
