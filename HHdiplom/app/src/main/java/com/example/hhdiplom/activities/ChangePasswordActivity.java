package com.example.hhdiplom.activities;

import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.ChangePasswordRequest;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ChangePasswordActivity extends AppCompatActivity {

    private TextInputLayout tilOldPassword;
    private TextInputLayout tilNewPassword;
    private TextInputLayout tilConfirmPassword;
    private TextInputEditText etOldPassword;
    private TextInputEditText etNewPassword;
    private TextInputEditText etConfirmPassword;
    private Button btnSavePassword;
    private ProgressBar progressBar;

    private ApiService apiService;
    private Call<Void> changePasswordCall;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_change_password);

        apiService = ApiClient.getApiService();

        tilOldPassword = findViewById(R.id.tilOldPassword);
        tilNewPassword = findViewById(R.id.tilNewPassword);
        tilConfirmPassword = findViewById(R.id.tilConfirmPassword);
        etOldPassword = findViewById(R.id.etOldPassword);
        etNewPassword = findViewById(R.id.etNewPassword);
        etConfirmPassword = findViewById(R.id.etConfirmPassword);
        btnSavePassword = findViewById(R.id.btnSavePassword);
        progressBar = findViewById(R.id.progressBar);
        ImageButton btnBack = findViewById(R.id.btnBack);

        btnBack.setOnClickListener(v -> finish());
        btnSavePassword.setOnClickListener(v -> submit());
    }

    private void submit() {
        clearErrors();

        String oldPassword = text(etOldPassword);
        String newPassword = text(etNewPassword);
        String confirmPassword = text(etConfirmPassword);

        boolean valid = true;

        if (TextUtils.isEmpty(oldPassword)) {
            tilOldPassword.setError(getString(R.string.change_password_error_old_required));
            valid = false;
        }
        if (TextUtils.isEmpty(newPassword)) {
            tilNewPassword.setError(getString(R.string.change_password_error_new_required));
            valid = false;
        } else if (newPassword.length() < 8) {
            tilNewPassword.setError(getString(R.string.change_password_error_new_min));
            valid = false;
        }
        if (TextUtils.isEmpty(confirmPassword)) {
            tilConfirmPassword.setError(getString(R.string.change_password_error_confirm_required));
            valid = false;
        } else if (!newPassword.equals(confirmPassword)) {
            tilConfirmPassword.setError(getString(R.string.change_password_error_mismatch));
            valid = false;
        }
        if (!TextUtils.isEmpty(oldPassword) && oldPassword.equals(newPassword)) {
            tilNewPassword.setError(getString(R.string.change_password_error_same));
            valid = false;
        }

        if (!valid) {
            return;
        }

        setLoading(true);
        ChangePasswordRequest body = new ChangePasswordRequest(oldPassword, newPassword, confirmPassword);
        changePasswordCall = apiService.changePassword(body);
        changePasswordCall.enqueue(new Callback<Void>() {
            @Override
            public void onResponse(Call<Void> call, Response<Void> response) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                setLoading(false);
                if (response.isSuccessful()) {
                    Toast.makeText(ChangePasswordActivity.this, getString(R.string.change_password_success), Toast.LENGTH_SHORT).show();
                    setResult(RESULT_OK);
                    finish();
                } else if (response.code() == 400) {
                    Toast.makeText(ChangePasswordActivity.this, getString(R.string.change_password_error_check_data), Toast.LENGTH_LONG).show();
                } else if (response.code() == 401) {
                    Toast.makeText(ChangePasswordActivity.this, getString(R.string.change_password_session_expired), Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(ChangePasswordActivity.this, getString(R.string.error_with_code, response.code()), Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onFailure(Call<Void> call, Throwable t) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                setLoading(false);
                Toast.makeText(ChangePasswordActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void clearErrors() {
        tilOldPassword.setError(null);
        tilNewPassword.setError(null);
        tilConfirmPassword.setError(null);
    }

    private void setLoading(boolean loading) {
        progressBar.setVisibility(loading ? View.VISIBLE : View.GONE);
        btnSavePassword.setEnabled(!loading);
    }

    private String text(TextInputEditText editText) {
        return editText.getText() == null ? "" : editText.getText().toString().trim();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (changePasswordCall != null && !changePasswordCall.isCanceled()) {
            changePasswordCall.cancel();
        }
    }
}
