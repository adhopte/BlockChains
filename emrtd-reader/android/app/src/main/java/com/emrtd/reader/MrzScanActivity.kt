package com.emrtd.reader

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Size
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import com.emrtd.reader.databinding.ActivityMrzScanBinding
import com.emrtd.reader.model.MrzData
import com.emrtd.reader.mrz.MrzParser
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MrzScanActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMrzScanBinding
    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private val detected = AtomicBoolean(false)

    private val requestPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startCamera() else finish()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMrzScanBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnManualEntry.setOnClickListener { showManualEntry() }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            == PackageManager.PERMISSION_GRANTED
        ) {
            startCamera()
        } else {
            requestPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.viewFinder.surfaceProvider)
            }
            val analysis = ImageAnalysis.Builder()
                .setTargetResolution(Size(1280, 720))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also {
                    it.setAnalyzer(cameraExecutor, MrzImageAnalyzer(::onMrzFound))
                }
            provider.unbindAll()
            provider.bindToLifecycle(
                this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis
            )
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onMrzFound(mrz: MrzData) {
        if (detected.compareAndSet(false, true)) {
            runOnUiThread {
                val intent = Intent(this, MainActivity::class.java).apply {
                    putExtra(MainActivity.EXTRA_MRZ_DATA, mrz)
                    flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                }
                startActivity(intent)
                finish()
            }
        }
    }

    private fun showManualEntry() {
        ManualMrzDialog { mrz -> onMrzFound(mrz) }
            .show(supportFragmentManager, "manual_mrz")
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
    }
}

class MrzImageAnalyzer(private val onMrz: (MrzData) -> Unit) : ImageAnalysis.Analyzer {
    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private val parser = MrzParser()

    @androidx.camera.core.ExperimentalGetImage
    override fun analyze(proxy: ImageProxy) {
        val media = proxy.image ?: run { proxy.close(); return }
        val img = InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees)
        recognizer.process(img)
            .addOnSuccessListener { text ->
                parser.parse(text.text)?.let { onMrz(it) }
                proxy.close()
            }
            .addOnFailureListener { proxy.close() }
    }
}
