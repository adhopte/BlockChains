# JMRTD
-keep class org.jmrtd.** { *; }
-keep class net.sf.scuba.** { *; }
-keep class org.ejbca.** { *; }
# Bouncy Castle
-keep class org.bouncycastle.** { *; }
-dontwarn org.bouncycastle.**
# Retrofit
-keepattributes Signature
-keepattributes Exceptions
-keep class retrofit2.** { *; }
-keep class com.emrtd.reader.model.** { *; }
