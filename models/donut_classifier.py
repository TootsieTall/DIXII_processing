import torch
from transformers import DonutSwinModel, DonutSwinPreTrainedModel, DonutProcessor
from torch import nn
from PIL import Image
import os

class DonutForImageClassification(DonutSwinPreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.swin = DonutSwinModel(config)
        self.dropout = nn.Dropout(0.5)
        self.classifier = nn.Linear(self.swin.num_features, config.num_labels)

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        outputs = self.swin(pixel_values)
        pooled_output = outputs[1]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits

class DonutTaxClassifier:
    def __init__(self, model_path):
        self.model_path = model_path
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.processor = None
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the donut model and processor"""
        try:
            self.processor = DonutProcessor.from_pretrained(self.model_path)
            self.model = DonutForImageClassification.from_pretrained(self.model_path)
            self.model.to(self.device)
            self.model.eval()
            print(f"Donut model loaded successfully on {self.device}")
        except Exception as e:
            print(f"Error loading donut model: {e}")
            self.processor = None
            self.model = None
    
    def classify_document(self, image_path):
        """
        Classify a tax document image
        Returns: (predicted_label, confidence_score)
        """
        if not self.model or not self.processor:
            return None, 0.0
        
        try:
            # Load and resize image
            img = Image.open(image_path)
            img_resized = img.resize((1920, 2560), Image.Resampling.LANCZOS)
            
            # Perform inference
            with torch.no_grad():
                pixel_values = self.processor(img_resized.convert("RGB"), return_tensors="pt", legacy=False).pixel_values
                pixel_values = pixel_values.to(self.device)
                outputs = self.model(pixel_values)
                
                # Get prediction
                probabilities = torch.nn.functional.softmax(outputs, dim=-1)
                confidence, predicted = torch.max(probabilities, 1)
                
                predicted_idx = predicted.cpu().numpy()[0]
                confidence_score = confidence.cpu().numpy()[0]
                predicted_label = self.model.config.id2label[predicted_idx]
                
                return predicted_label, float(confidence_score)
                
        except Exception as e:
            print(f"Error classifying document: {e}")
            return None, 0.0
    
    def get_human_readable_label(self, label):
        """Convert model label to human-readable format"""
        label_mapping = {
            "1040": "1040",
            "1040_sch_1": "1040 Schedule 1",
            "1040_sch_2": "1040 Schedule 2", 
            "1040_sch_3": "1040 Schedule 3",
            "1040_sch_8812": "1040 Schedule 8812",
            "1040_sch_a": "1040 Schedule A",
            "1040_sch_b": "1040 Schedule B",
            "1040_sch_c": "1040 Schedule C",
            "1040_sch_d": "1040 Schedule D",
            "1040_sch_e": "1040 Schedule E",
            "1040_sch_se": "1040 Schedule SE",
            "1040nr": "1040-NR",
            "1040nr_sch_oi": "1040-NR Schedule OI",
            "form_1125": "1125-A",
            "form_8949": "8949",
            "form_8959": "8959",
            "form_8960": "8960",
            "form_8995": "8995",
            "form_8995_sch_a": "8995 Schedule A",
            "letter": "Letter",
            "other_misc": "Misc",
            "w2": "W-2"
        }
        return label_mapping.get(label, label) 