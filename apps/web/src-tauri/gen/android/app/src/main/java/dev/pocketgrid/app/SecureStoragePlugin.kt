package dev.pocketgrid.app

import android.app.Activity
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import app.tauri.annotation.Command
import app.tauri.annotation.InvokeArg
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.JSObject
import app.tauri.plugin.Plugin
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

@InvokeArg
class SecretKeyArgs {
    lateinit var key: String
}

@InvokeArg
class SecretValueArgs {
    lateinit var key: String
    lateinit var value: String
}

/**
 * Session tokens and device credentials, sealed with AES-GCM under a
 * non-exportable Android Keystore key. Only ciphertext reaches SharedPreferences,
 * and app backup is disabled, so a copied or restored value cannot be decrypted.
 */
@TauriPlugin
class SecureStoragePlugin(private val activity: Activity) : Plugin(activity) {
    private val prefs = activity.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)

    private fun secretKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    private fun read(key: String): String? {
        val stored = prefs.getString(key, null) ?: return null
        return try {
            val sealed = Base64.decode(stored, Base64.NO_WRAP)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, sealed, 0, IV_BYTES))
            String(cipher.doFinal(sealed, IV_BYTES, sealed.size - IV_BYTES), Charsets.UTF_8)
        } catch (error: Exception) {
            // A value sealed by another key (reinstall, restore) reads as signed out.
            prefs.edit().remove(key).apply()
            null
        }
    }

    @Command
    fun getSecret(invoke: Invoke) {
        val args = invoke.parseArgs(SecretKeyArgs::class.java)
        val result = JSObject()
        result.put("value", read(args.key) ?: "")
        result.put("found", prefs.contains(args.key))
        invoke.resolve(result)
    }

    @Command
    fun setSecret(invoke: Invoke) {
        val args = invoke.parseArgs(SecretValueArgs::class.java)
        try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, secretKey())
            val sealed = cipher.iv + cipher.doFinal(args.value.toByteArray(Charsets.UTF_8))
            if (!prefs.edit().putString(args.key, Base64.encodeToString(sealed, Base64.NO_WRAP)).commit()) {
                invoke.reject("Secure storage could not save")
                return
            }
            invoke.resolve()
        } catch (error: Exception) {
            invoke.reject("Secure storage unavailable")
        }
    }

    @Command
    fun deleteSecret(invoke: Invoke) {
        val args = invoke.parseArgs(SecretKeyArgs::class.java)
        if (!prefs.edit().remove(args.key).commit()) {
            invoke.reject("Secure storage could not clear")
            return
        }
        invoke.resolve()
    }

    companion object {
        private const val KEY_ALIAS = "dev.pocketgrid.app.secure-storage"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val IV_BYTES = 12
    }
}
