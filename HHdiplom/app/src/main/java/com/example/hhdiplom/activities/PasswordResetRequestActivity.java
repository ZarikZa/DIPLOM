package com.example.hhdiplom.activities;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.PasswordResetRequest;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class PasswordResetRequestActivity extends AppCompatActivity {

    private TextInputLayout emailLayout;
    private TextInputEditText etEmail;
    private Button btnSendCode;

    private ApiService apiService;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_password_reset_request);

        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        emailLayout = findViewById(R.id.emailLayout);
        etEmail = findViewById(R.id.etEmail);
        btnSendCode = findViewById(R.id.btnSendCode);

        btnSendCode.setOnClickListener(v -> {
            emailLayout.setError(null);

            String email = etEmail.getText() == null ? "" : etEmail.getText().toString().trim();
            if (email.isEmpty()) {
                emailLayout.setError(getString(R.string.password_reset_request_email_required));
                return;
            }
            if (!android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
                emailLayout.setError(getString(R.string.password_reset_request_email_invalid));
                return;
            }

            setLoading(true);

            apiService.passwordResetRequest(new PasswordResetRequest(email))
                    .enqueue(new Callback<Void>() {
                        @Override
                        public void onResponse(Call<Void> call, Response<Void> response) {
                            setLoading(false);

                            Toast.makeText(
                                    PasswordResetRequestActivity.this,
                                    getString(R.string.password_reset_request_code_sent),
                                    Toast.LENGTH_LONG
                            ).show();

                            Intent intent = new Intent(PasswordResetRequestActivity.this, PasswordResetConfirmActivity.class);
                            intent.putExtra("email", email);
                            startActivity(intent);
                            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                            finish();
                        }

                        @Override
                        public void onFailure(Call<Void> call, Throwable t) {
                            setLoading(false);
                            String message = t.getMessage() == null ? getString(R.string.login_network_unknown) : t.getMessage();
                            Toast.makeText(
                                    PasswordResetRequestActivity.this,
                                    getString(R.string.error_network_with_message, message),
                                    Toast.LENGTH_SHORT
                            ).show();
                        }
                    });
        });
    }

    private void setLoading(boolean loading) {
        btnSendCode.setEnabled(!loading);
        btnSendCode.setText(loading
                ? getString(R.string.password_reset_request_sending)
                : getString(R.string.password_reset_request_send_code));
        etEmail.setEnabled(!loading);
    }

    @Override
    public void onBackPressed() {
        super.onBackPressed();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    }
}
