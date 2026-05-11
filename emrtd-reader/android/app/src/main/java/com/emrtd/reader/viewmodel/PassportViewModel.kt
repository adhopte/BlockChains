package com.emrtd.reader.viewmodel

import android.nfc.tech.IsoDep
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.emrtd.reader.api.ApiClient
import com.emrtd.reader.model.*
import com.emrtd.reader.nfc.PassportReader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

sealed class ReadingState {
    object Idle : ReadingState()
    object Reading : ReadingState()
    data class ChipResult(val result: EmrtdResult) : ReadingState()
    data class ApiResult(val response: EmrtdValidationResponse) : ReadingState()
    data class Error(val message: String) : ReadingState()
}

class PassportViewModel : ViewModel() {

    private val _state = MutableLiveData<ReadingState>(ReadingState.Idle)
    val state: LiveData<ReadingState> = _state

    fun readPassport(isoDep: IsoDep, mrzData: MrzData) {
        _state.value = ReadingState.Reading
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) {
                    PassportReader().readPassport(isoDep, mrzData)
                }
                _state.value = ReadingState.ChipResult(result)

                // After on-device reading, send to backend for full validation
                sendToBackend(result)
            } catch (e: Exception) {
                _state.value = ReadingState.Error(e.message ?: "Unknown error")
            }
        }
    }

    private suspend fun sendToBackend(result: EmrtdResult) {
        try {
            val personalData = result.personalData?.let {
                PersonalDataRequest(
                    surname = it.surname,
                    givenNames = it.givenNames,
                    nationality = it.nationality,
                    dateOfBirth = it.dateOfBirth,
                    sex = it.sex,
                    dateOfExpiry = it.dateOfExpiry,
                    documentNumber = it.documentNumber,
                    issuingCountry = it.issuingCountry,
                    optionalData = it.optionalData
                )
            }

            val request = EmrtdValidationRequest(
                documentNumber = result.mrzInfo?.documentNumber ?: "",
                personalData = personalData,
                bacOrPacePerformed = result.securityChecks.bacOrPacePerformed,
                bacSuccess = result.securityChecks.bacSuccess,
                paceSuccess = result.securityChecks.paceSuccess,
                sodBytes = result.rawSodHex,
                dgHashes = result.dgHashesHex.ifEmpty { null },
                aaPublicKey = result.aaPublicKeyHex,
                aaChallenge = result.aaChallengeHex,
                aaResponse = result.aaResponseHex,
                aaAlgorithm = result.aaAlgorithm,
                chipAuthPublicKey = result.chipAuthPublicKeyHex,
                chipAuthOid = result.chipAuthOid,
                dataGroupsRead = result.dataGroups
            )

            val response = withContext(Dispatchers.IO) {
                ApiClient.service.validateEmrtd(request)
            }

            if (response.isSuccessful) {
                response.body()?.let { _state.value = ReadingState.ApiResult(it) }
            } else {
                // Still show chip result even if backend unreachable
            }
        } catch (e: Exception) {
            // Backend call failed; chip result already set
        }
    }
}
