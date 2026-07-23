package com.minicpmv.app.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cloud
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.minicpmv.app.data.entity.SettingKeys
import com.minicpmv.app.service.RecognitionForegroundService
import com.minicpmv.app.viewmodel.MainViewModel

/**
 * 设置页面 - 自动识别、云端授权、预算限额、数据同步
 */
@Composable
fun SettingsScreen(
    modifier: Modifier = Modifier,
    snackbarHostState: SnackbarHostState,
    viewModel: MainViewModel = viewModel()
) {
    val context = androidx.compose.ui.platform.LocalContext.current

    var autoRecognition by remember { mutableStateOf(false) }
    var cloudEnabled by remember { mutableStateOf(false) }
    var syncWifiOnly by remember { mutableStateOf(true) }
    var confidenceThreshold by remember { mutableFloatStateOf(0.7f) }
    var dailyBudget by remember { mutableFloatStateOf(10f) }

    // 加载设置
    LaunchedEffect(Unit) {
        viewModel.loadSettings()
        autoRecognition = viewModel.getSettingBoolean(SettingKeys.AUTO_RECOGNITION, false)
        cloudEnabled = viewModel.getSettingBoolean(SettingKeys.CLOUD_ENABLED, false)
        syncWifiOnly = viewModel.getSettingBoolean(SettingKeys.SYNC_WIFI_ONLY, true)
        confidenceThreshold = viewModel.getSettingBoolean(SettingKeys.CONFIDENCE_THRESHOLD, false)
            .let { if (it) 0.8f else 0.7f }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "设置",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        // 识别设置
        SettingsSection(title = "识别") {
            SwitchSettingItem(
                title = "后台自动识别",
                subtitle = "定时拍照并自动识别场景",
                icon = Icons.Filled.Notifications,
                checked = autoRecognition,
                onCheckedChange = {
                    autoRecognition = it
                    viewModel.setSetting(SettingKeys.AUTO_RECOGNITION, it.toString())
                    if (it) {
                        RecognitionForegroundService.start(context)
                    } else {
                        RecognitionForegroundService.stop(context)
                    }
                }
            )

            SliderSettingItem(
                title = "置信度阈值",
                subtitle = "低于此值将请求云端识别",
                value = confidenceThreshold,
                onValueChange = {
                    confidenceThreshold = it
                    viewModel.setSetting(SettingKeys.CONFIDENCE_THRESHOLD, it.toString())
                },
                valueRange = 0.5f..0.95f
            )
        }

        // 云端设置
        SettingsSection(title = "云端") {
            SwitchSettingItem(
                title = "启用云端 API",
                subtitle = "端侧置信度不足时请求云端",
                icon = Icons.Filled.Cloud,
                checked = cloudEnabled,
                onCheckedChange = {
                    cloudEnabled = it
                    viewModel.setSetting(SettingKeys.CLOUD_ENABLED, it.toString())
                }
            )

            SliderSettingItem(
                title = "日预算限额",
                subtitle = "云端 API 每日消费上限（元）",
                value = dailyBudget,
                onValueChange = {
                    dailyBudget = it
                    viewModel.setSetting(SettingKeys.DAILY_BUDGET, it.toString())
                },
                valueRange = 0f..50f,
                steps = 49
            )
        }

        // 同步设置
        SettingsSection(title = "数据同步") {
            SwitchSettingItem(
                title = "仅 WiFi 同步",
                subtitle = "避免使用移动数据流量",
                icon = Icons.Filled.Sync,
                checked = syncWifiOnly,
                onCheckedChange = {
                    syncWifiOnly = it
                    viewModel.setSetting(SettingKeys.SYNC_WIFI_ONLY, it.toString())
                }
            )

            Button(
                onClick = { viewModel.triggerSync() },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Filled.Sync, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("立即同步")
            }
        }

        // 安全设置
        SettingsSection(title = "安全") {
            ListItem(
                headlineContent = { Text("数据库加密") },
                supportingContent = { Text("SQLCipher AES-256 加密已启用") },
                leadingContent = { Icon(Icons.Filled.Lock, contentDescription = null) }
            )
        }
    }
}

@Composable
private fun SettingsSection(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Column {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
        )
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(vertical = 8.dp)) {
                content()
            }
        }
    }
}

@Composable
private fun SwitchSettingItem(
    title: String,
    subtitle: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    ListItem(
        headlineContent = { Text(title) },
        supportingContent = { Text(subtitle) },
        leadingContent = { Icon(icon, contentDescription = null) },
        trailingContent = {
            Switch(checked = checked, onCheckedChange = onCheckedChange)
        }
    )
}

@Composable
private fun SliderSettingItem(
    title: String,
    subtitle: String,
    value: Float,
    onValueChange: (Float) -> Unit,
    valueRange: ClosedFloatingPointRange<Float> = 0f..1f,
    steps: Int = 0
) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(title, style = MaterialTheme.typography.bodyLarge)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(
                text = "%.2f".format(value),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.primary
            )
        }
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = valueRange,
            steps = steps,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
