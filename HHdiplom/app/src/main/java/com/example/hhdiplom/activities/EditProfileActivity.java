package com.example.hhdiplom.activities;

import android.app.DatePickerDialog;
import android.net.Uri;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.Patterns;
import android.view.View;
import android.widget.ImageButton;
import android.webkit.MimeTypeMap;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;

import com.bumptech.glide.Glide;
import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.UserProfile;
import com.example.hhdiplom.utils.ProfanityValidator;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Locale;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.RequestBody;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class EditProfileActivity extends AppCompatActivity {

    private TextInputLayout tilFirstName;
    private TextInputLayout tilLastName;
    private TextInputLayout tilEmail;
    private TextInputLayout tilPhone;
    private TextInputLayout tilBirthDate;
    private TextInputLayout tilResume;
    private TextInputLayout tilCompanyName;
    private TextInputLayout tilCompanyNumber;
    private TextInputLayout tilCompanyIndustry;
    private TextInputLayout tilCompanyDescription;

    private TextInputEditText etFirstName;
    private TextInputEditText etLastName;
    private TextInputEditText etEmail;
    private TextInputEditText etPhone;
    private TextInputEditText etBirthDate;
    private TextInputEditText etResume;
    private TextInputEditText etCompanyName;
    private TextInputEditText etCompanyNumber;
    private TextInputEditText etCompanyIndustry;
    private TextInputEditText etCompanyDescription;

    private ImageView ivProfilePhoto;
    private TextView tvRoleInfo;
    private TextView tvPhotoHint;
    private TextView tvApplicantSectionTitle;
    private TextView tvCompanySectionTitle;
    private View cardCompanySection;
    private Button btnChangePhoto;
    private Button btnSave;
    private ProgressBar progressBar;

    private ApiService apiService;
    private UserProfile currentProfile;
    private boolean isContentManager;
    private Uri selectedAvatarUri;
    private boolean avatarChanged;

    private ActivityResultLauncher<String> pickPhotoLauncher;

    private Call<UserProfile> loadProfileCall;
    private Call<UserProfile> updateProfileCall;
    private Call<UserProfile> uploadAvatarCall;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_edit_profile);

        apiService = ApiClient.getApiService();
        pickPhotoLauncher = registerForActivityResult(
                new ActivityResultContracts.GetContent(),
                uri -> {
                    if (uri == null || isContentManager) {
                        return;
                    }
                    selectedAvatarUri = uri;
                    avatarChanged = true;
                    loadAvatarPreview(uri);
                }
        );

        findViews();
        setupDatePicker();
        loadCurrentProfile();
        ImageButton btnBack = findViewById(R.id.btnBack);
        btnBack.setOnClickListener(v -> finish());

        btnChangePhoto.setOnClickListener(v -> {
            if (!isContentManager) {
                pickPhotoLauncher.launch("image/*");
            }
        });
        btnSave.setOnClickListener(v -> saveProfile());
    }

    private void findViews() {
        tilFirstName = findViewById(R.id.tilFirstName);
        tilLastName = findViewById(R.id.tilLastName);
        tilEmail = findViewById(R.id.tilEmail);
        tilPhone = findViewById(R.id.tilPhone);
        tilBirthDate = findViewById(R.id.tilBirthDate);
        tilResume = findViewById(R.id.tilResume);
        tilCompanyName = findViewById(R.id.tilCompanyName);
        tilCompanyNumber = findViewById(R.id.tilCompanyNumber);
        tilCompanyIndustry = findViewById(R.id.tilCompanyIndustry);
        tilCompanyDescription = findViewById(R.id.tilCompanyDescription);

        etFirstName = findViewById(R.id.etFirstName);
        etLastName = findViewById(R.id.etLastName);
        etEmail = findViewById(R.id.etEmail);
        etPhone = findViewById(R.id.etPhone);
        etBirthDate = findViewById(R.id.etBirthDate);
        etResume = findViewById(R.id.etResume);
        etCompanyName = findViewById(R.id.etCompanyName);
        etCompanyNumber = findViewById(R.id.etCompanyNumber);
        etCompanyIndustry = findViewById(R.id.etCompanyIndustry);
        etCompanyDescription = findViewById(R.id.etCompanyDescription);

        ivProfilePhoto = findViewById(R.id.ivProfilePhoto);
        tvRoleInfo = findViewById(R.id.tvRoleInfo);
        tvPhotoHint = findViewById(R.id.tvPhotoHint);
        tvApplicantSectionTitle = findViewById(R.id.tvApplicantSectionTitle);
        tvCompanySectionTitle = findViewById(R.id.tvCompanySectionTitle);
        cardCompanySection = findViewById(R.id.cardCompanySection);
        btnChangePhoto = findViewById(R.id.btnChangePhoto);
        btnSave = findViewById(R.id.btnSave);
        progressBar = findViewById(R.id.progressBar);
    }

    private void setupDatePicker() {
        etBirthDate.setOnClickListener(v -> {
            if (isContentManager) {
                return;
            }

            Calendar calendar = Calendar.getInstance();
            String current = safeText(etBirthDate);
            if (!current.isEmpty() && current.contains(".")) {
                try {
                    String[] parts = current.split("\\.");
                    calendar.set(
                            Integer.parseInt(parts[2]),
                            Integer.parseInt(parts[1]) - 1,
                            Integer.parseInt(parts[0])
                    );
                } catch (Exception ignored) {
                }
            }

            DatePickerDialog picker = new DatePickerDialog(
                    this,
                    (view, year, month, dayOfMonth) -> etBirthDate.setText(String.format(
                            Locale.getDefault(),
                            "%02d.%02d.%d",
                            dayOfMonth,
                            month + 1,
                            year
                    )),
                    calendar.get(Calendar.YEAR),
                    calendar.get(Calendar.MONTH),
                    calendar.get(Calendar.DAY_OF_MONTH)
            );
            picker.show();
        });
    }

    private void loadCurrentProfile() {
        if (isFinishing() || isDestroyed()) {
            return;
        }

        setLoading(true);
        loadProfileCall = apiService.getUserProfile();
        loadProfileCall.enqueue(new Callback<UserProfile>() {
            @Override
            public void onResponse(Call<UserProfile> call, Response<UserProfile> response) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                if (response.isSuccessful() && response.body() != null) {
                    currentProfile = response.body();
                    isContentManager = isContentManagerProfile(currentProfile);
                    applyRoleVisibility();
                    fillProfileFields(currentProfile);
                    setLoading(false);
                } else {
                    setLoading(false);
                    Toast.makeText(EditProfileActivity.this, getString(R.string.edit_profile_load_failed), Toast.LENGTH_SHORT).show();
                    finish();
                }
            }

            @Override
            public void onFailure(Call<UserProfile> call, Throwable t) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                setLoading(false);
                Toast.makeText(EditProfileActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
                finish();
            }
        });
    }

    private void applyRoleVisibility() {
        tvRoleInfo.setText(isContentManager
                ? getString(R.string.edit_profile_role_cm)
                : getString(R.string.edit_profile_role_applicant));

        int applicantVisibility = isContentManager ? View.GONE : View.VISIBLE;
        int companyVisibility = View.GONE;

        btnChangePhoto.setVisibility(applicantVisibility);
        tvPhotoHint.setText(isContentManager
                ? getString(R.string.edit_profile_photo_hint_cm)
                : getString(R.string.edit_profile_photo_hint_applicant));
        if (isContentManager) {
            avatarChanged = false;
            selectedAvatarUri = null;
        }

        tvApplicantSectionTitle.setVisibility(applicantVisibility);
        tilBirthDate.setVisibility(applicantVisibility);
        tilResume.setVisibility(applicantVisibility);

        cardCompanySection.setVisibility(companyVisibility);
        tvCompanySectionTitle.setVisibility(companyVisibility);
        tilCompanyName.setVisibility(companyVisibility);
        tilCompanyNumber.setVisibility(companyVisibility);
        tilCompanyIndustry.setVisibility(companyVisibility);
        tilCompanyDescription.setVisibility(companyVisibility);
    }

    private void fillProfileFields(UserProfile profile) {
        etFirstName.setText(nonNull(profile.getFirstName()));
        etLastName.setText(nonNull(profile.getLastName()));
        etEmail.setText(nonNull(profile.getEmail()));
        etPhone.setText(nonNull(profile.getPhone()));
        loadAvatarPreview(profile.getAvatar());

        if (!isContentManager) {
            etBirthDate.setText(formatBirthDateForUi(profile.getBirthDate()));
            etResume.setText(nonNull(profile.getResume()));
        }
    }

    private void saveProfile() {
        if (currentProfile == null || isFinishing() || isDestroyed()) {
            return;
        }

        clearErrors();
        if (!validateForm()) {
            return;
        }

        setLoading(true);

        UserProfile updated = new UserProfile();
        updated.setFirstName(safeText(etFirstName));
        updated.setLastName(safeText(etLastName));
        updated.setEmail(safeText(etEmail));
        updated.setPhone(safeText(etPhone));

        if (!isContentManager) {
            String birthIso = parseBirthDateForApi(safeText(etBirthDate));
            if (!birthIso.isEmpty()) {
                updated.setBirthDate(birthIso);
            }
            updated.setResume(safeText(etResume));
        }

        updateProfileCall = apiService.updateProfile(updated);
        updateProfileCall.enqueue(new Callback<UserProfile>() {
            @Override
            public void onResponse(Call<UserProfile> call, Response<UserProfile> response) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                if (response.isSuccessful() && response.body() != null) {
                    currentProfile = response.body();
                    ApiClient.saveUserInfo(currentProfile);
                    if (isContentManager) {
                        onSaveSuccess();
                    } else {
                        uploadAvatarIfNeeded();
                    }
                } else {
                    setLoading(false);
                    btnSave.setEnabled(true);
                    Toast.makeText(EditProfileActivity.this, buildErrorMessage(response.code(), response.errorBody() != null), Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onFailure(Call<UserProfile> call, Throwable t) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                setLoading(false);
                btnSave.setEnabled(true);
                Toast.makeText(EditProfileActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void uploadAvatarIfNeeded() {
        if (isContentManager || !avatarChanged || selectedAvatarUri == null) {
            onSaveSuccess();
            return;
        }

        MultipartBody.Part avatarPart = buildAvatarPart(selectedAvatarUri);
        if (avatarPart == null) {
            setLoading(false);
            btnSave.setEnabled(true);
            Toast.makeText(this, getString(R.string.edit_profile_warning_avatar_prepare_failed), Toast.LENGTH_LONG).show();
            return;
        }

        uploadAvatarCall = apiService.uploadProfileAvatar(avatarPart);
        uploadAvatarCall.enqueue(new Callback<UserProfile>() {
            @Override
            public void onResponse(Call<UserProfile> call, Response<UserProfile> response) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }

                if (response.isSuccessful()) {
                    if (response.body() != null) {
                        currentProfile = response.body();
                        ApiClient.saveUserInfo(currentProfile);
                        loadAvatarPreview(currentProfile.getAvatar());
                    }
                    avatarChanged = false;
                    selectedAvatarUri = null;
                    onSaveSuccess();
                } else {
                    setLoading(false);
                    btnSave.setEnabled(true);
                    Toast.makeText(EditProfileActivity.this, getString(R.string.edit_profile_warning_avatar_not_uploaded), Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onFailure(Call<UserProfile> call, Throwable t) {
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                setLoading(false);
                btnSave.setEnabled(true);
                Toast.makeText(EditProfileActivity.this, getString(R.string.edit_profile_warning_avatar_not_uploaded), Toast.LENGTH_LONG).show();
            }
        });
    }

    private MultipartBody.Part buildAvatarPart(Uri uri) {
        try {
            String mimeType = getContentResolver().getType(uri);
            if (TextUtils.isEmpty(mimeType)) {
                mimeType = "image/jpeg";
            }

            String extension = MimeTypeMap.getSingleton().getExtensionFromMimeType(mimeType);
            if (TextUtils.isEmpty(extension)) {
                extension = "jpg";
            }

            File tempFile = new File(getCacheDir(), "applicant_avatar_upload." + extension);
            copyUriToFile(uri, tempFile);

            RequestBody fileBody = RequestBody.create(MediaType.parse(mimeType), tempFile);
            return MultipartBody.Part.createFormData("avatar", tempFile.getName(), fileBody);
        } catch (Exception e) {
            return null;
        }
    }

    private void copyUriToFile(Uri sourceUri, File targetFile) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(sourceUri);
             FileOutputStream out = new FileOutputStream(targetFile, false)) {
            if (in == null) {
                throw new IOException("Input stream is null");
            }
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            out.flush();
        }
    }

    private void onSaveSuccess() {
        setLoading(false);
        btnSave.setEnabled(true);
        Toast.makeText(this, getString(R.string.edit_profile_save_success), Toast.LENGTH_SHORT).show();
        setResult(RESULT_OK);
        finish();
    }

    private boolean validateForm() {
        boolean valid = true;

        String firstName = safeText(etFirstName);
        String lastName = safeText(etLastName);
        String email = safeText(etEmail);
        String phone = safeText(etPhone);
        String resume = safeText(etResume);
        String companyName = safeText(etCompanyName);
        String companyIndustry = safeText(etCompanyIndustry);
        String companyDescription = safeText(etCompanyDescription);

        if (TextUtils.isEmpty(firstName)) {
            tilFirstName.setError(getString(R.string.edit_profile_error_first_name_required));
            valid = false;
        } else if (ProfanityValidator.containsProfanity(firstName)) {
            tilFirstName.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            valid = false;
        }

        if (TextUtils.isEmpty(lastName)) {
            tilLastName.setError(getString(R.string.edit_profile_error_last_name_required));
            valid = false;
        } else if (ProfanityValidator.containsProfanity(lastName)) {
            tilLastName.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            valid = false;
        }

        if (TextUtils.isEmpty(email)) {
            tilEmail.setError(getString(R.string.edit_profile_error_email_required));
            valid = false;
        } else if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            tilEmail.setError(getString(R.string.edit_profile_error_email_invalid));
            valid = false;
        }

        if (!TextUtils.isEmpty(phone) && !phone.matches("^[0-9+()\\-\\s]{7,20}$")) {
            tilPhone.setError(getString(R.string.edit_profile_error_phone_invalid));
            valid = false;
        }

        if (!isContentManager) {
            String birth = safeText(etBirthDate);
            if (!TextUtils.isEmpty(birth) && parseBirthDateForApi(birth).isEmpty()) {
                tilBirthDate.setError(getString(R.string.edit_profile_error_birth_date_invalid));
                valid = false;
            }

            if (!TextUtils.isEmpty(resume) && ProfanityValidator.containsProfanity(resume)) {
                tilResume.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
                valid = false;
            }
        }

        if (!TextUtils.isEmpty(companyName) && ProfanityValidator.containsProfanity(companyName)) {
            tilCompanyName.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            valid = false;
        }

        if (!TextUtils.isEmpty(companyIndustry) && ProfanityValidator.containsProfanity(companyIndustry)) {
            tilCompanyIndustry.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            valid = false;
        }

        if (!TextUtils.isEmpty(companyDescription) && ProfanityValidator.containsProfanity(companyDescription)) {
            tilCompanyDescription.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            valid = false;
        }

        return valid;
    }

    private void clearErrors() {
        tilFirstName.setError(null);
        tilLastName.setError(null);
        tilEmail.setError(null);
        tilPhone.setError(null);
        tilBirthDate.setError(null);
        tilResume.setError(null);
        tilCompanyName.setError(null);
        tilCompanyNumber.setError(null);
        tilCompanyIndustry.setError(null);
        tilCompanyDescription.setError(null);
    }

    private boolean isContentManagerProfile(UserProfile profile) {
        String role = profile.getEmployeeRole();
        return role != null && role.toLowerCase().contains("content");
    }

    private void setLoading(boolean loading) {
        progressBar.setVisibility(loading ? View.VISIBLE : View.GONE);
        btnSave.setEnabled(!loading);
    }

    private void loadAvatarPreview(Uri localUri) {
        Glide.with(this)
                .load(localUri)
                .placeholder(R.drawable.ic_profile)
                .error(R.drawable.ic_profile)
                .circleCrop()
                .into(ivProfilePhoto);
    }

    private void loadAvatarPreview(String avatarPath) {
        String avatarUrl = resolveAbsoluteUrl(avatarPath);
        Glide.with(this)
                .load(avatarUrl)
                .placeholder(R.drawable.ic_profile)
                .error(R.drawable.ic_profile)
                .circleCrop()
                .into(ivProfilePhoto);
    }

    private String resolveAbsoluteUrl(String value) {
        if (TextUtils.isEmpty(value)) {
            return null;
        }
        if (value.startsWith("http://") || value.startsWith("https://")) {
            return value;
        }
        String normalized = value.startsWith("/") ? value.substring(1) : value;
        return ApiClient.BASE_URL + normalized;
    }

    private String formatBirthDateForUi(String apiBirthDate) {
        if (TextUtils.isEmpty(apiBirthDate)) {
            return "";
        }

        try {
            SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
            SimpleDateFormat ui = new SimpleDateFormat("dd.MM.yyyy", Locale.getDefault());
            return ui.format(iso.parse(apiBirthDate));
        } catch (Exception ignored) {
            return apiBirthDate;
        }
    }

    private String parseBirthDateForApi(String uiBirthDate) {
        if (TextUtils.isEmpty(uiBirthDate)) {
            return "";
        }

        String[] parts = uiBirthDate.split("\\.");
        if (parts.length != 3) {
            return "";
        }

        try {
            int day = Integer.parseInt(parts[0]);
            int month = Integer.parseInt(parts[1]);
            int year = Integer.parseInt(parts[2]);
            if (day < 1 || day > 31 || month < 1 || month > 12 || year < 1900) {
                return "";
            }
            return String.format(Locale.US, "%04d-%02d-%02d", year, month, day);
        } catch (Exception ignored) {
            return "";
        }
    }

    private String safeText(TextInputEditText editText) {
        return editText.getText() == null ? "" : editText.getText().toString().trim();
    }

    private String nonNull(String value) {
        return value == null ? "" : value;
    }

    private String buildErrorMessage(int code, boolean hasBody) {
        if (code == 400) {
            return getString(R.string.edit_profile_error_validation);
        }
        if (code == 401) {
            return getString(R.string.session_expired_login_again);
        }
        if (hasBody) {
            return getString(R.string.edit_profile_error_update_code, code);
        }
        return getString(R.string.error_with_code, code);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();

        if (loadProfileCall != null && !loadProfileCall.isCanceled()) {
            loadProfileCall.cancel();
        }
        if (updateProfileCall != null && !updateProfileCall.isCanceled()) {
            updateProfileCall.cancel();
        }
        if (uploadAvatarCall != null && !uploadAvatarCall.isCanceled()) {
            uploadAvatarCall.cancel();
        }
    }
}
