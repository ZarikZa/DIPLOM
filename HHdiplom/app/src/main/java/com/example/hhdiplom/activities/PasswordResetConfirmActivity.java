package com.example.hhdiplom.activities;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.PasswordResetConfirm;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class PasswordResetConfirmActivity extends AppCompatActivity {

    private TextView tvEmail;
    private TextInputLayout codeLayout;
    private TextInputLayout passLayout;
    private TextInputEditText etCode;
    private TextInputEditText etNewPassword;
    private Button btnConfirm;

    private ApiService apiService;
    private String email;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_password_reset_confirm);

        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        email = getIntent().getStringExtra("email");
        if (email == null) {
            email = "";
        }

        tvEmail = findViewById(R.id.tvEmail);
        codeLayout = findViewById(R.id.codeLayout);
        passLayout = findViewById(R.id.passLayout);
        etCode = findViewById(R.id.etCode);
        etNewPassword = findViewById(R.id.etNewPassword);
        btnConfirm = findViewById(R.id.btnConfirm);

        tvEmail.setText(getString(R.string.password_reset_confirm_email_template, email));

        btnConfirm.setOnClickListener(v -> {
            codeLayout.setError(null);
            passLayout.setError(null);

            String code = etCode.getText() == null ? "" : etCode.getText().toString().trim();
            String newPass = etNewPassword.getText() == null ? "" : etNewPassword.getText().toString().trim();

            boolean hasError = false;

            if (code.length() != 6) {
                codeLayout.setError(getString(R.string.password_reset_confirm_code_error));
                hasError = true;
            }

            if (newPass.length() < 6) {
                passLayout.setError(getString(R.string.password_reset_confirm_password_error));
                hasError = true;
            }

            if (hasError) {
                return;
            }

            setLoading(true);

            apiService.passwordResetConfirm(new PasswordResetConfirm(email, code, newPass))
                    .enqueue(new Callback<Void>() {
                        @Override
                        public void onResponse(Call<Void> call, Response<Void> response) {
                            setLoading(false);

                            if (response.isSuccessful()) {
                                Toast.makeText(
                                        PasswordResetConfirmActivity.this,
                                        getString(R.string.password_reset_confirm_success),
                                        Toast.LENGTH_LONG
                                ).show();

                                ApiClient.clearTokens();

                                Intent intent = new Intent(PasswordResetConfirmActivity.this, LoginActivity.class);
                                intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
                                startActivity(intent);
                                finish();
                            } else {
                                if (response.code() == 400) {
                                    codeLayout.setError(getString(R.string.password_reset_confirm_invalid_code));
                                } else {
                                    Toast.makeText(
                                            PasswordResetConfirmActivity.this,
                                            getString(R.string.error_with_code, response.code()),
                                            Toast.LENGTH_SHORT
                                    ).show();
                                }
                            }
                        }

                        @Override
                        public void onFailure(Call<Void> call, Throwable t) {
                            setLoading(false);
                            String message = t.getMessage() == null ? getString(R.string.login_network_unknown) : t.getMessage();
                            Toast.makeText(
                                    PasswordResetConfirmActivity.this,
                                    getString(R.string.error_network_with_message, message),
                                    Toast.LENGTH_SHORT
                            ).show();
                        }
                    });
        });
    }

    private void setLoading(boolean loading) {
        btnConfirm.setEnabled(!loading);
        btnConfirm.setText(loading
                ? getString(R.string.password_reset_confirm_processing)
                : getString(R.string.password_reset_confirm_button));
        etCode.setEnabled(!loading);
        etNewPassword.setEnabled(!loading);
    }

    @Override
    public void onBackPressed() {
        super.onBackPressed();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    }
}
