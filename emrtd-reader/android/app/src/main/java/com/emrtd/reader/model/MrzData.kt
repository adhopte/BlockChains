package com.emrtd.reader.model

import android.os.Parcelable
import kotlinx.parcelize.Parcelize

@Parcelize
data class MrzData(
    val documentNumber: String,
    val dateOfBirth: String,   // YYMMDD
    val dateOfExpiry: String,  // YYMMDD
    val surname: String = "",
    val givenNames: String = "",
    val nationality: String = "",
    val sex: String = "",
    val issuingCountry: String = ""
) : Parcelable
