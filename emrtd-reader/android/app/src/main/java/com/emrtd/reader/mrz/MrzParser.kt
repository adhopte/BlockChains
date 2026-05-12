package com.emrtd.reader.mrz

import com.emrtd.reader.model.MrzData

class MrzParser {

    fun parse(rawText: String): MrzData? {
        // Normalise: keep alphanumeric and '<', uppercase
        val lines = rawText.lines()
            .map { it.filter { c -> c.isLetterOrDigit() || c == '<' }.uppercase().trim() }
            .filter { it.length >= 30 }

        // TD3 (passport): 2 lines × 44 chars
        for (i in 0 until lines.size - 1) {
            if (lines[i].length >= 44 && lines[i + 1].length >= 44) {
                parseTD3(lines[i].take(44), lines[i + 1].take(44))?.let { return it }
            }
        }

        // TD1 (ID card): 3 lines × 30 chars
        for (i in 0 until lines.size - 2) {
            if (lines[i].length >= 30 && lines[i + 1].length >= 30 && lines[i + 2].length >= 30) {
                parseTD1(
                    lines[i].take(30),
                    lines[i + 1].take(30),
                    lines[i + 2].take(30)
                )?.let { return it }
            }
        }

        return null
    }

    private fun parseTD3(line1: String, line2: String): MrzData? {
        return try {
            // line1: P<CCCPRIMARYIDENTIFIER<<SECONDARYIDENTIFIER
            // line2: DOCNUMCHKNATDOB<CHKSEXEXPIRY<CHKOPTIONAL<OVERALLCHK
            if (line1[0] != 'P') return null  // must be passport

            val issuingCountry = line1.substring(2, 5).trimEnd('<')
            val nameField = line1.substring(5)
            val nameParts = nameField.split("<<")
            val surname = nameParts.getOrNull(0)?.replace('<', ' ')?.trim() ?: ""
            val givenNames = nameParts.getOrNull(1)?.replace('<', ' ')?.trim() ?: ""

            val docNumber = line2.substring(0, 9).trimEnd('<')
            val docChk = line2[9]
            val nationality = line2.substring(10, 13).trimEnd('<')
            val dob = line2.substring(13, 19)
            val dobChk = line2[19]
            val sex = line2[20].toString()
            val expiry = line2.substring(21, 27)
            val expiryChk = line2[27]

            if (!checkDigit(docNumber, docChk)) return null
            if (!checkDigit(dob, dobChk)) return null
            if (!checkDigit(expiry, expiryChk)) return null

            MrzData(docNumber, dob, expiry, surname, givenNames, nationality, sex, issuingCountry)
        } catch (e: Exception) {
            null
        }
    }

    private fun parseTD1(line1: String, line2: String, line3: String): MrzData? {
        return try {
            val issuingCountry = line1.substring(2, 5).trimEnd('<')
            val docNumber = line1.substring(5, 14).trimEnd('<')
            val docChk = line1[14]

            val dob = line2.substring(0, 6)
            val dobChk = line2[6]
            val sex = line2[7].toString()
            val expiry = line2.substring(8, 14)
            val expiryChk = line2[14]
            val nationality = line2.substring(15, 18).trimEnd('<')

            val nameParts = line3.split("<<")
            val surname = nameParts.getOrNull(0)?.replace('<', ' ')?.trim() ?: ""
            val givenNames = nameParts.getOrNull(1)?.replace('<', ' ')?.trim() ?: ""

            if (!checkDigit(docNumber, docChk)) return null
            if (!checkDigit(dob, dobChk)) return null
            if (!checkDigit(expiry, expiryChk)) return null

            MrzData(docNumber, dob, expiry, surname, givenNames, nationality, sex, issuingCountry)
        } catch (e: Exception) {
            null
        }
    }

    private fun checkDigit(data: String, check: Char): Boolean {
        val weights = intArrayOf(7, 3, 1)
        var sum = 0
        data.forEachIndexed { i, c ->
            val v = when {
                c.isDigit() -> c.digitToInt()
                c in 'A'..'Z' -> c.code - 'A'.code + 10
                else -> 0
            }
            sum += v * weights[i % 3]
        }
        return (sum % 10).toString()[0] == check
    }
}
