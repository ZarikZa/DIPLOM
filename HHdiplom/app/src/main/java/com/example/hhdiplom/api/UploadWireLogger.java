package com.example.hhdiplom.api;

import android.util.Log;
import java.io.IOException;
import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;

public class UploadWireLogger implements Interceptor {
    @Override public Response intercept(Chain chain) throws IOException {
        Request r = chain.request();
        String url = r.url().toString();

        // логируем только upload эндпоинт
        if (!url.contains("/api/content-manager/videos/") && !url.contains("/api/vacancy-videos/")) {
            return chain.proceed(r);
        }

        long t0 = System.currentTimeMillis();
        Log.e("UPLOAD_WIRE", "==> " + r.method() + " " + url);
        Log.e("UPLOAD_WIRE", "==> headers:\n" + r.headers());

        try {
            Response resp = chain.proceed(r);
            long dt = System.currentTimeMillis() - t0;
            Log.e("UPLOAD_WIRE", "<== code=" + resp.code() + " in " + dt + "ms");
            return resp;
        } catch (Exception e) {
            long dt = System.currentTimeMillis() - t0;
            Log.e("UPLOAD_WIRE", "<xx FAIL in " + dt + "ms: " + e.getClass().getSimpleName() + " " + e.getMessage(), e);
            throw e;
        }
    }
}
