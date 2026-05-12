package com.emrtd.reader

import android.app.Dialog
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.DialogFragment
import com.emrtd.reader.databinding.DialogManualMrzBinding
import com.emrtd.reader.model.MrzData
import com.emrtd.reader.mrz.MrzParser

class ManualMrzDialog(private val onResult: (MrzData) -> Unit) : DialogFragment() {

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        val binding = DialogManualMrzBinding.inflate(layoutInflater)
        return AlertDialog.Builder(requireContext())
            .setTitle("Enter MRZ data manually")
            .setView(binding.root)
            .setPositiveButton("Use") { _, _ ->
                val docNum = binding.etDocNumber.text.toString().uppercase().trim()
                val dob = binding.etDateOfBirth.text.toString().trim()
                val expiry = binding.etDateOfExpiry.text.toString().trim()
                if (docNum.isBlank() || dob.length != 6 || expiry.length != 6) {
                    Toast.makeText(requireContext(), "Invalid input", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                onResult(MrzData(docNum, dob, expiry))
            }
            .setNegativeButton("Cancel", null)
            .create()
    }
}
