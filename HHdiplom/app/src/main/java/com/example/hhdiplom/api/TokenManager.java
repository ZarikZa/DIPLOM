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
     * ✅ FIX:
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

        // ✅ во время загрузки пропускаем refresh, чтобы не убивать Worker и не разлогинивать
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
                // на всякий: считаем сетью/временной ошибкой, не фейлим вход
                Log.e(TAG, "checkAndRefreshToken crashed: " + t.getMessage(), t);
                postRefreshed(callback);
                return;
            }

            if (success) {
                postRefreshed(callback);
                return;
            }

            // Если refresh не удался:
            // ✅ если access token всё ещё есть — скорее всего это сеть, не выкидываем на логин
            // ❌ если access token уже очищен (сервер отверг refresh) — тогда это реальный fail
            if (ApiClient.getAccessToken() != null) {
                Log.w(TAG, "Refresh failed but token still present -> treat as network issue");
                postRefreshed(callback);
            } else {
                postFailed(callback, "Failed to refresh token");
            }
        }).start();
    }

    /**
     * Принудительный refresh по кнопке/ручной команде.
     * ✅ Во время upload — НЕ делаем (иначе опять всё ломается).
     * ✅ Если сеть — не считаем фаталом.
     */
    public static void forceRefreshToken(Context context, TokenRefreshCallback callback) {
        ApiClient.init(context);

        if (!ApiClient.isLoggedIn()) {
            callback.onTokenRefreshFailed("Not logged in");
            return;
        }

        if (UploadGate.isUploading()) {
            Log.w(TAG, "Skip force refresh: upload in progress");
            callback.onTokenRefreshed();
            return;
        }

        new Thread(() -> {
            try {
                boolean success = ApiClient.refreshToken();
                if (success) {
                    postRefreshed(callback);
                    return;
                }

                // ✅ если access token остался — считаем временной/сетевой ошибкой
                if (ApiClient.getAccessToken() != null) {
                    Log.w(TAG, "Force refresh failed but token still present -> treat as network issue");
                    postRefreshed(callback);
                } else {
                    postFailed(callback, "Failed to refresh token");
                }

            } catch (Throwable t) {
                // ✅ сеть/таймаут/прочее — не фейлим вход
                if (isLikelyNetwork(t)) {
                    Log.w(TAG, "Force refresh network error -> ignore: " + t.getMessage());
                    postRefreshed(callback);
                } else {
                    Log.e(TAG, "Force refresh error: " + t.getMessage(), t);
                    postFailed(callback, "Refresh error: " + t.getMessage());
                }
            }
        }).start();
    }

    private static boolean isLikelyNetwork(Throwable t) {
        Throwable c = t;
        while (c != null) {
            if (c instanceof SocketTimeoutException
                    || c instanceof UnknownHostException
                    || c instanceof ConnectException
                    || c instanceof IOException) {
                return true;
            }
            c = c.getCause();
        }
        return false;
    }

    // callback-и сейчас вызываются из background thread и раньше так было.
    // Если у тебя UI требует main thread — скажи, я добавлю Handler/Looper.
    private static void postRefreshed(TokenRefreshCallback callback) {
        if (callback != null) callback.onTokenRefreshed();
    }

    private static void postFailed(TokenRefreshCallback callback, String error) {
        if (callback != null) callback.onTokenRefreshFailed(error);
    }
}
