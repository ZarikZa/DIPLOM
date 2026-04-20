package com.example.hhdiplom.api;

import android.util.Log;

import java.io.IOException;

import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class RequestDebugInterceptor implements Interceptor {
    private static final String TAG = "HTTP_DEBUG";

    @Override
    public Response intercept(Chain chain) throws IOException {
        Request req = chain.request();
        RequestBody body = req.body();

        String ct = (body != null && body.contentType() != null) ? body.contentType().toString() : "null";
        long len = -1;
        if (body != null) {
            try { len = body.contentLength(); } catch (Exception ignored) {}
        }

        Log.d(TAG, ">>> " + req.method() + " " + req.url());
        Log.d(TAG, ">>> headers:\n" + req.headers());
        Log.d(TAG, ">>> body.contentType=" + ct + " body.contentLength=" + len);

        try {
            Response resp = chain.proceed(req);
            Log.d(TAG, "<<< " + resp.code() + " " + resp.message() + " for " + req.url());
            return resp;
        } catch (Exception e) {
            Log.e(TAG, "xxx FAILED for " + req.url() + " : " + e.getClass().getSimpleName() + " " + e.getMessage(), e);
            throw e;
        }
    }
}
