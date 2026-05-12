package com.emrtd.reader

import android.app.Application
import org.bouncycastle.jce.provider.BouncyCastleProvider
import java.security.Security

class EmrtdApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Replace the default BC provider with the full Bouncy Castle
        // so JMRTD crypto operations work correctly on Android.
        Security.removeProvider("BC")
        Security.insertProviderAt(BouncyCastleProvider(), 1)
    }
}
