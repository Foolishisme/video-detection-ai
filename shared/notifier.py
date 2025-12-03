#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报警通知模块
支持多种通知方式：控制台、文件、邮件、Webhook
"""

import logging
import os
import json
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, Tuple


class AlertNotifier:
    """
    报警通知管理器 - 网络请求和发邮件逻辑
    
    功能：
    - 支持多种通知方式：控制台、文件、邮件、Webhook
    - 可配置的通知模板和节流机制
    - 网络请求（Webhook）和邮件发送功能
    
    注意：触发逻辑需要在新项目中自定义实现
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化报警通知管理器
        
        Args:
            config_path: 配置文件路径（可选），如果不提供则使用默认配置
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.enabled = self.config.get("enabled", True)
        
        # 日志配置
        self.logger = logging.getLogger('AlertNotifier')
        
        # 通知方法映射
        self.notification_methods = {
            "console": self._send_console,
            "file": self._send_file,
            "email": self._send_email,
            "webhook": self._send_webhook
        }
        
        # 确保日志目录存在
        if self.config["methods"].get("file", {}).get("enabled", False):
            log_file = self.config["methods"]["file"].get("file_path", "alerts/alerts_log.txt")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"加载配置文件失败: {e}，使用默认配置")
        
        # 返回默认配置
        return {
            "enabled": True,
            "methods": {
                "console": {
                    "enabled": True,
                    "min_severity": "低"
                },
                "file": {
                    "enabled": True,
                    "min_severity": "低",
                    "file_path": "alerts/alerts_log.txt"
                },
                "email": {
                    "enabled": False,
                    "min_severity": "中",
                    "smtp_server": "smtp.example.com",
                    "smtp_port": 587,
                    "username": "alert_system@example.com",
                    "password": "your_password_here",
                    "from_address": "alert_system@example.com",
                    "to_addresses": ["admin@example.com"],
                    "use_tls": True
                },
                "webhook": {
                    "enabled": False,
                    "min_severity": "中",
                    "url": "https://example.com/webhook",
                    "headers": {
                        "Content-Type": "application/json",
                        "Authorization": "Bearer your_token_here"
                    },
                    "method": "POST"
                }
            },
            "alert_templates": {
                "low": {
                    "subject": "低严重性警报: {rule_name}",
                    "body": "检测到低严重性事件:\n规则: {rule_name}\n描述: {description}\n时间: {timestamp}\n位置: {location}"
                },
                "medium": {
                    "subject": "中严重性警报: {rule_name}",
                    "body": "检测到中严重性事件:\n规则: {rule_name}\n描述: {description}\n时间: {timestamp}\n位置: {location}\n\n请及时查看和处理。"
                },
                "high": {
                    "subject": "高严重性警报: {rule_name}",
                    "body": "检测到高严重性事件:\n规则: {rule_name}\n描述: {description}\n时间: {timestamp}\n位置: {location}\n\n请立即查看和处理！"
                }
            }
        }
    
    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        发送报警通知（核心接口）
        
        Args:
            alert_data: 报警数据字典，应包含以下字段：
                - rule_name: 规则名称
                - description: 描述
                - severity: 严重性（"低"、"中"、"高"）
                - location: 位置（可选）
                - timestamp: 时间戳（可选，默认使用当前时间）
        
        Returns:
            bool: 发送成功返回True，否则返回False
        
        示例：
            alert_data = {
                "rule_name": "异常行为检测",
                "description": "检测到可疑活动",
                "severity": "高",
                "location": "摄像头1"
            }
            notifier.send_alert(alert_data)
        """
        if not self.enabled:
            self.logger.debug("报警功能已禁用")
            return False
        
        # 准备通知内容
        subject, body = self._format_message(alert_data)
        
        # 遍历所有启用的通知方法
        success = False
        for method_name, method_config in self.config["methods"].items():
            if not method_config.get("enabled", False):
                continue
            
            # 检查严重性级别
            if not self._check_severity(method_config, alert_data):
                continue
            
            # 调用对应的通知方法
            if method_name in self.notification_methods:
                try:
                    self.notification_methods[method_name](alert_data, subject, body, method_config)
                    success = True
                except Exception as e:
                    self.logger.error(f"发送 {method_name} 通知失败: {str(e)}")
        
        return success
    
    def _check_severity(self, method_config: Dict, alert_data: Dict) -> bool:
        """检查严重性级别是否满足要求"""
        min_severity = method_config.get("min_severity", "低")
        alert_severity = alert_data.get("severity", "低")
        
        severity_levels = {"低": 1, "中": 2, "高": 3}
        return severity_levels.get(alert_severity, 0) >= severity_levels.get(min_severity, 0)
    
    def _format_message(self, alert_data: Dict) -> Tuple[str, str]:
        """格式化通知消息"""
        severity = alert_data.get("severity", "低").lower()
        severity_map = {"低": "low", "中": "medium", "高": "high"}
        template_key = severity_map.get(severity, "low")
        
        templates = self.config.get("alert_templates", {})
        template = templates.get(template_key, {})
        
        subject_template = template.get("subject", "告警: {rule_name}")
        body_template = template.get("body", "检测到告警:\n规则: {rule_name}\n描述: {description}\n时间: {timestamp}")
        
        # 准备模板变量
        timestamp = alert_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        location = alert_data.get("location", "未知位置")
        
        # 替换模板变量
        subject = subject_template.format(
            rule_name=alert_data.get("rule_name", "未知规则"),
            description=alert_data.get("description", "无描述"),
            timestamp=timestamp,
            location=location
        )
        
        body = body_template.format(
            rule_name=alert_data.get("rule_name", "未知规则"),
            description=alert_data.get("description", "无描述"),
            timestamp=timestamp,
            location=location
        )
        
        return subject, body
    
    def _send_console(self, alert_data: Dict, subject: str, body: str, config: Dict):
        """发送控制台通知"""
        print(f"\n[告警] {subject}")
        print("-" * 50)
        print(body)
        print("-" * 50)
    
    def _send_file(self, alert_data: Dict, subject: str, body: str, config: Dict):
        """发送文件通知"""
        file_path = config.get("file_path", "alerts/alerts_log.txt")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {subject}\n")
            f.write("-" * 50 + "\n")
            f.write(body + "\n")
            f.write("-" * 50 + "\n")
    
    def _send_email(self, alert_data: Dict, subject: str, body: str, config: Dict):
        """
        发送邮件通知（核心功能）
        
        配置要求：
            - smtp_server: SMTP服务器地址
            - smtp_port: SMTP端口（默认587）
            - username: SMTP用户名
            - password: SMTP密码
            - from_address: 发件人地址
            - to_addresses: 收件人地址列表
            - use_tls: 是否使用TLS（默认True）
        """
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 587)
        username = config.get("username")
        password = config.get("password")
        from_address = config.get("from_address")
        to_addresses = config.get("to_addresses", [])
        use_tls = config.get("use_tls", True)
        
        if not all([smtp_server, username, password, from_address, to_addresses]):
            self.logger.error("邮件配置不完整")
            return
        
        try:
            # 创建邮件消息
            msg = MIMEMultipart()
            msg['From'] = from_address
            msg['To'] = ", ".join(to_addresses)
            msg['Subject'] = subject
            
            # 添加正文
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 连接SMTP服务器并发送
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.sendmail(from_address, to_addresses, msg.as_string())
            server.quit()
            
            self.logger.info(f"邮件通知已发送到: {', '.join(to_addresses)}")
            
        except Exception as e:
            self.logger.error(f"发送邮件失败: {str(e)}")
            raise
    
    def _send_webhook(self, alert_data: Dict, subject: str, body: str, config: Dict):
        """
        发送Webhook通知（核心功能 - 网络请求）
        
        配置要求：
            - url: Webhook URL
            - headers: 请求头字典（可选）
            - method: 请求方法（"POST"或"GET"，默认POST）
        """
        url = config.get("url")
        headers = config.get("headers", {})
        method = config.get("method", "POST").upper()
        
        if not url:
            self.logger.error("Webhook配置不完整：缺少URL")
            return
        
        # 准备请求数据
        payload = {
            "subject": subject,
            "body": body,
            "alert": alert_data,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # 发送HTTP请求
            if method == "POST":
                response = requests.post(url, json=payload, headers=headers, timeout=10)
            else:
                response = requests.get(url, params=payload, headers=headers, timeout=10)
            
            # 检查响应状态
            if 200 <= response.status_code < 300:
                self.logger.info(f"Webhook通知成功发送: {url}")
            else:
                self.logger.warning(f"Webhook返回非成功状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"发送Webhook通知失败: {str(e)}")
            raise

