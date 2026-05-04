package com.example.hhdiplom.api;

import android.content.Context;
import android.util.Log;

import java.io.IOException;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;

public class TokenManager {

    private static final String TAG = "TokenManager";

    public interface TokenRefreshCallback {
        void onTokenRefreshed();
        void onTokenRefreshFailed(String error);
    }

    /**
     * 1) Во время upload (UploadGate.isUploading()) — НЕ делаем refresh вообще.
     * 2) Если refresh не удался из-за сети (таймаут/нет хоста/нет соединения) — НЕ считаем это "фаталом"
     *    и НЕ выкидываем на Login. Просто вызываем onTokenRefreshed(), чтобы приложение продолжало жить.
     * 3) Реально "failed" только если токены реально инвалидны (refreshToken() сам очистит токены на 400/401).
     */
    public static void checkTokenOnAppStart(Context context, TokenRefreshCallback callback) {
        ApiClient.init(context);

        if (!ApiClient.isLoggedIn()) {
            callback.onTokenRefreshFailed("Not logged in");
            return;
        }

        if (UploadGate.isUploading()) {
            Log.w(TAG, "Skip refresh on app start: upload in progress");
            callback.onTokenRefreshed();
            return;
        }

        new Thread(() -> {
            boolean success;
            try {
                success = ApiClient.checkAndRefreshToken();
            } catch (Throwable t) {
                Log.e(TAG, "checkAndRefreshToken crashed: " + t.getMessage(), t);
                postRefreshed(callback);
                return;
            }

            if (success) {
                postRefreshed(callback);
                return;
            }

            if (ApiClient.getAccessToken() != null) {
                Log.w(TAG, "Refresh failed but token still present -> treat as network issue");
                postRefreshed(callback);
            } else {
                postFailed(callback, "Failed to refresh token");
            }
        }).start();
    }


    private static void postRefreshed(TokenRefreshCallback callback) {
        if (callback != null) callback.onTokenRefreshed();
    }

    private static void postFailed(TokenRefreshCallback callback, String error) {
        if (callback != null) callback.onTokenRefreshFailed(error);
    }
}
