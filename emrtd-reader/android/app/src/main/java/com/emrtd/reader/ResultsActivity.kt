package com.emrtd.reader

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.emrtd.reader.databinding.ActivityResultsBinding
import com.emrtd.reader.model.EmrtdValidationResponse
import com.google.gson.Gson
import com.google.gson.GsonBuilder

class ResultsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityResultsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityResultsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val response: EmrtdValidationResponse? = intent.getSerializableExtra(EXTRA_API_RESULT)
            as? EmrtdValidationResponse

        if (response == null) {
            binding.tvOverall.text = "No result data"
            return
        }

        val checks = response.securityChecks
        binding.tvOverall.text = if (response.overallValid) "✅ DOCUMENT VALID" else "❌ DOCUMENT INVALID"
        binding.tvOverall.setTextColor(
            if (response.overallValid) 0xFF27AE60.toInt() else 0xFFE74C3C.toInt()
        )

        val sb = StringBuilder()
        sb.append("=== Personal Data ===\n")
        response.personalData?.let { pd ->
            sb.append("Name:        ${pd.surname}, ${pd.givenNames}\n")
            sb.append("Nationality: ${pd.nationality}\n")
            sb.append("DOB:         ${pd.dateOfBirth}\n")
            sb.append("Expiry:      ${pd.dateOfExpiry}\n")
            sb.append("Sex:         ${pd.sex}\n")
            sb.append("Doc No:      ${pd.documentNumber}\n")
            sb.append("Issuer:      ${pd.issuingCountry}\n")
        } ?: sb.append("Not available\n")

        sb.append("\n=== Security Checks ===\n")
        sb.append("Auth method:     ${checks.bacOrPacePerformed}\n")
        sb.append("BAC:             ${checks.bacSuccess.yn()}\n")
        sb.append("PACE:            ${checks.paceSuccess.yn()}\n")
        sb.append("Passive Auth:    ${checks.passiveAuthSuccess.yn()}")
        checks.passiveAuthError?.let { sb.append(" ($it)") }
        sb.append("\n")
        sb.append("Active Auth:     ${checks.activeAuthSuccess.yn()}")
        checks.activeAuthError?.let { sb.append(" ($it)") }
        sb.append("\n")
        sb.append("Chip Auth:       ${checks.chipAuthSuccess.yn()}")
        checks.chipAuthError?.let { sb.append(" ($it)") }
        sb.append("\n")
        sb.append("EAC:             ${checks.eacSuccess.yn()}")
        checks.eacError?.let { sb.append(" ($it)") }
        sb.append("\n")

        sb.append("\n=== Data Groups Read ===\n")
        response.dataGroupsRead.entries
            .sortedBy { it.key }
            .forEach { (dg, ok) -> sb.append("$dg: ${if (ok) "✓" else "✗"}\n") }

        sb.append("\n=== Raw JSON ===\n")
        sb.append(GsonBuilder().setPrettyPrinting().create().toJson(response))

        binding.tvDetails.text = sb.toString()
    }

    private fun Boolean.yn() = if (this) "PASS" else "FAIL"

    companion object {
        const val EXTRA_API_RESULT = "extra_api_result"
    }
}
