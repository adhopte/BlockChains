package com.emrtd.reader.api

import com.emrtd.reader.model.EmrtdValidationRequest
import com.emrtd.reader.model.EmrtdValidationResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface EmrtdApiService {

    @GET("health")
    suspend fun healthCheck(): Response<Map<String, String>>

    @POST("api/v1/validate")
    suspend fun validateEmrtd(
        @Body request: EmrtdValidationRequest
    ): Response<EmrtdValidationResponse>
}
