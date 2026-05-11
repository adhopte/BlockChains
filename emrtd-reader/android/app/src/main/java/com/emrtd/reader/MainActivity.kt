package com.emrtd.reader

import android.app.PendingIntent
import android.content.Intent
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.IsoDep
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import com.emrtd.reader.databinding.ActivityMainBinding
import com.emrtd.reader.model.MrzData
import com.emrtd.reader.viewmodel.PassportViewModel
import com.emrtd.reader.viewmodel.ReadingState

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: PassportViewModel by viewModels()
    private var nfcAdapter: NfcAdapter? = null
    private var pendingMrzData: MrzData? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        nfcAdapter = NfcAdapter.getDefaultAdapter(this)
        if (nfcAdapter == null) {
            Toast.makeText(this, "NFC not supported on this device", Toast.LENGTH_LONG).show()
        }

        binding.btnScanMrz.setOnClickListener {
            startActivity(Intent(this, MrzScanActivity::class.java))
        }

        viewModel.state.observe(this) { state ->
            when (state) {
                is ReadingState.Idle -> {
                    binding.progressBar.visibility = View.GONE
                    binding.tvStatus.text = "Scan MRZ first, then hold passport to NFC reader"
                }
                is ReadingState.Reading -> {
                    binding.progressBar.visibility = View.VISIBLE
                    binding.tvStatus.text = "Reading passport chip…"
                }
                is ReadingState.ChipResult -> {
                    binding.progressBar.visibility = View.VISIBLE
                    binding.tvStatus.text = "Sending to backend for validation…"
                }
                is ReadingState.ApiResult -> {
                    binding.progressBar.visibility = View.GONE
                    val intent = Intent(this, ResultsActivity::class.java)
                    intent.putExtra(ResultsActivity.EXTRA_API_RESULT, state.response)
                    startActivity(intent)
                }
                is ReadingState.Error -> {
                    binding.progressBar.visibility = View.GONE
                    binding.tvStatus.text = "Error: ${state.message}"
                    Toast.makeText(this, state.message, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        pendingMrzData = intent.getParcelableExtra(EXTRA_MRZ_DATA)
        if (pendingMrzData != null) {
            binding.tvStatus.text = "MRZ ready. Hold passport to phone NFC — back of phone"
            enableNfcDispatch()
        }
        if (nfcAdapter?.isEnabled == false) {
            Toast.makeText(this, "Please enable NFC in Settings", Toast.LENGTH_LONG).show()
        }
    }

    override fun onPause() {
        super.onPause()
        nfcAdapter?.disableForegroundDispatch(this)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.getParcelableExtra<Tag>(NfcAdapter.EXTRA_TAG)?.let { tag ->
            processTag(tag)
        }
    }

    private fun enableNfcDispatch() {
        val pending = PendingIntent.getActivity(
            this, 0,
            Intent(this, javaClass).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_MUTABLE
        )
        nfcAdapter?.enableForegroundDispatch(this, pending, null, null)
    }

    private fun processTag(tag: Tag) {
        val isoDep = IsoDep.get(tag)
        if (isoDep == null) {
            Toast.makeText(this, "Not an ISO-DEP NFC tag", Toast.LENGTH_SHORT).show()
            return
        }
        val mrz = pendingMrzData
        if (mrz == null) {
            Toast.makeText(this, "Please scan MRZ first", Toast.LENGTH_SHORT).show()
            return
        }
        viewModel.readPassport(isoDep, mrz)
    }

    companion object {
        const val EXTRA_MRZ_DATA = "extra_mrz_data"
    }
}
